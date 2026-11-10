"""VoiceAssistant high-level facade for host integration."""
from __future__ import annotations

import inspect
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from voicecore.asr.whistle import WhistleASR
from voicecore.audio.capture import AudioCapture
from voicecore.audio.hotkey import HotkeyListener
from voicecore.config import VoiceCoreConfig
from voicecore.engine import set_threads
from voicecore.events import (
    ConfirmRequestEvent,
    DoneEvent,
    ErrorEvent,
    Event,
    EventBus,
    GateEvent,
    ListeningStartedEvent,
    ListeningStoppedEvent,
    NoSpeechEvent,
    ReminderDueEvent,
    RouteEvent,
    ToolResultEvent,
    TranscriptEvent,
)
from voicecore.nlu.base import ToolCall
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import ReminderManager, set_reminder, set_reminder_precheck
from voicecore.tools.registry import ToolDefinition, ToolRegistry


EVENT_NAME_MAP: Dict[str, Type[Event]] = {
    "transcript": TranscriptEvent,
    "confirm_request": ConfirmRequestEvent,
    "tool_result": ToolResultEvent,
    "reminder_due": ReminderDueEvent,
    "route": RouteEvent,
    "gate": GateEvent,
    "error": ErrorEvent,
    "done": DoneEvent,
    "listening_started": ListeningStartedEvent,
    "listening_stopped": ListeningStoppedEvent,
    "no_speech": NoSpeechEvent,
}


class VoiceAssistant:
    """High-level public facade exposing VoiceCore as a Python plugin/library.
    
    Guarantees:
    - Host tools go through the exact same PolicyGate, tiers, and event bus as built-ins.
    - Host-provided tools default to always-CONFIRM unless they supply both an approved
      tier (T0 or T1) and an explicit precheck function.
    - Model weights are loaded once; thread pools are configured deterministically.
    """

    def __init__(
        self,
        config: VoiceCoreConfig,
        registry: Optional[ToolRegistry] = None,
        event_bus: Optional[EventBus] = None,
        asr: Optional[WhistleASR] = None,
        router: Optional[NeedleRouter] = None,
        policy_gate: Optional[PolicyGate] = None,
        assistant: Optional[Assistant] = None,
        load_builtins: bool = True,
    ) -> None:
        self.config = config
        self.event_bus = event_bus or EventBus()
        self.registry = registry or ToolRegistry()

        # Deterministic threading configuration
        set_threads(self.config.runtime.threads)

        # Wire built-in tools if requested
        self.reminder_mgr: Optional[ReminderManager] = None
        if load_builtins:
            self._load_builtins()

        self.policy_gate = policy_gate or PolicyGate(
            config=self.config.policy,
            registry=self.registry,
        )

        self.router = router or NeedleRouter(
            registry=self.registry,
            stateless=True,
        )

        self.asr = asr or WhistleASR(
            config=self.config.asr,
            debug_config=self.config.debug,
        )

        self.assistant = assistant or Assistant(
            router=self.router,
            registry=self.registry,
            policy_gate=self.policy_gate,
            asr=self.asr,
            config=self.config,
            event_bus=self.event_bus,
        )

        self.audio_capture: Optional[AudioCapture] = None
        self.hotkey_listener: Optional[HotkeyListener] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._running = False

    def _load_builtins(self) -> None:
        """Register the built-in P0 tool suite with prechecks and triggers."""
        self.registry.register(
            open_app,
            tier="T1",
            name="open_app",
            precheck=open_app_precheck,
            triggers=["open", "launch", "start", "run", "calculator", "calc", "notepad"],
            is_host=False,
            has_explicit_tier=True,
        )

        search_files_triggers = ["search", "find", "locate", "files", "lookup"]
        self.registry.register(
            search_files,
            tier="T0",
            name="search_files",
            precheck=search_files_precheck,
            triggers=search_files_triggers,
            is_host=False,
            has_explicit_tier=True,
        )

        self.reminder_mgr = ReminderManager(
            on_due=lambda r: self.event_bus.publish(
                ReminderDueEvent(
                    run_id="background",
                    reminder_id=str(r.id),
                    message=r.message,
                    when=r.target_time_iso,
                )
            ),
        )
        self.reminder_mgr.reload_pending()

        def _set_reminder_wrapper(when: str, message: str) -> dict:
            return self.reminder_mgr.set_reminder(message=message, when=when)

        _set_reminder_wrapper.__doc__ = set_reminder.__doc__
        set_reminder_triggers = ["remind", "reminder", "schedule", "alarm", "timer"]
        self.registry.register(
            _set_reminder_wrapper,
            tier="T1",
            name="set_reminder",
            precheck=set_reminder_precheck,
            triggers=set_reminder_triggers,
            is_host=False,
            has_explicit_tier=True,
        )

    @classmethod
    def from_config(
        cls,
        config_path_or_config: Union[str, Path, VoiceCoreConfig] = "config/voicecore.toml",
        load_builtins: bool = True,
    ) -> VoiceAssistant:
        """Initialize VoiceAssistant from a TOML configuration file or object."""
        if isinstance(config_path_or_config, VoiceCoreConfig):
            cfg = config_path_or_config
        else:
            p = Path(config_path_or_config)
            if not p.is_file():
                # Try finding relative to package or current directory
                alt = Path(__file__).resolve().parent.parent.parent.parent / p
                if alt.is_file():
                    p = alt
            cfg = VoiceCoreConfig.from_toml(p)
        return cls(config=cfg, load_builtins=load_builtins)

    def register(
        self,
        fn: Callable[..., Any],
        tier: Optional[str] = None,
        precheck: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None,
        triggers: Optional[List[str]] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ToolDefinition:
        """Register a host tool.
        
        Host-provided tools default to always-CONFIRM unless they supply both:
        1. An explicit approved tier ('T0' or 'T1')
        2. An explicit precheck callable
        """
        # Resolve attributes from @tool decorator if attached
        resolved_tier = tier if tier is not None else getattr(fn, "_voicecore_tier", None)
        resolved_precheck = precheck if precheck is not None else getattr(fn, "_voicecore_precheck", None)
        resolved_triggers = triggers if triggers is not None else getattr(fn, "_voicecore_triggers", None)
        resolved_name = name if name is not None else getattr(fn, "_voicecore_name", None)
        target_name = resolved_name or fn.__name__
        existing = self.registry.get(target_name)
        if existing and not existing.is_host:
            raise ValueError(
                f"Cannot register host tool under built-in name '{target_name}'. Built-in tools cannot be overwritten."
            )

        resolved_desc = description if description is not None else getattr(fn, "_voicecore_description", None)

        # Host tools default to tier T1 if tier not specified
        has_explicit_tier = resolved_tier is not None
        effective_tier = resolved_tier if has_explicit_tier else "T1"

        tool_def = self.registry.register(
            fn=fn,
            tier=effective_tier,
            name=resolved_name,
            description=resolved_desc,
            precheck=resolved_precheck,
            triggers=resolved_triggers,
            is_host=True,
            has_explicit_tier=has_explicit_tier,
        )

        # Re-synchronize router so NeedleAgent picks up the new schema and triggers
        if hasattr(self.router, "sync_tools"):
            self.router.sync_tools()

        return tool_def

    def on(
        self,
        event_name_or_type: Union[str, Type[Event]],
        handler: Callable[[Any], None],
    ) -> None:
        """Subscribe a callback to an event type by string name or Event class."""
        if isinstance(event_name_or_type, str):
            key = event_name_or_type.lower().strip()
            if key not in EVENT_NAME_MAP:
                raise ValueError(
                    f"Unknown event name '{event_name_or_type}'. "
                    f"Available events: {list(EVENT_NAME_MAP.keys())}"
                )
            event_cls = EVENT_NAME_MAP[key]
        elif inspect.isclass(event_name_or_type) and issubclass(event_name_or_type, Event):
            event_cls = event_name_or_type
        else:
            raise TypeError(f"Expected event name string or Event class, got: {type(event_name_or_type)}")

        self.event_bus.subscribe(event_cls, handler)

    def warmup(self) -> None:
        """Perform one-time warmup inference for ASR and NLU."""
        self.assistant.warmup()

    def run_text(
        self,
        text: str,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the core pipeline from text input (bypassing mic/ASR)."""
        return self.assistant.run_text(text=text, confirmer=confirmer)

    def run_audio(
        self,
        audio_data: Any,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the full speech pipeline from audio array or WAV path."""
        return self.assistant.run_audio(audio_data=audio_data, confirmer=confirmer)

    def run_push_to_talk(
        self,
        confirmer: Optional[Callable[[ToolCall], bool]] = None,
    ) -> None:
        """Run a blocking push-to-talk loop using the configured hotkey."""
        self.audio_capture = AudioCapture(config=self.config.audio)
        self.hotkey_listener = HotkeyListener(
            config=self.config.hotkey,
            on_press=self.audio_capture.start,
            on_release=self._on_audio_released,
        )
        self._confirmer = confirmer
        self.hotkey_listener.listen()

    def _on_audio_released(self, press_duration_s: float) -> None:
        """Callback invoked when the push-to-talk hotkey is released."""
        if not self.audio_capture:
            return
        audio = self.audio_capture.stop()
        if audio is None:
            return
        self.run_audio(audio, confirmer=getattr(self, "_confirmer", None))

    def start(self, confirmer: Optional[Callable[[ToolCall], bool]] = None) -> None:
        """Start push-to-talk listening in a background thread."""
        if self._running:
            return
        self._running = True
        self._listener_thread = threading.Thread(
            target=self.run_push_to_talk,
            args=(confirmer,),
            daemon=True,
            name="VoiceAssistantListener",
        )
        self._listener_thread.start()

    def stop(self) -> None:
        """Stop background push-to-talk listener and release resources."""
        self._running = False
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.reminder_mgr:
            self.reminder_mgr.cancel_all()
