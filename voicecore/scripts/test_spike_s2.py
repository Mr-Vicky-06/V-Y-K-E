import json
import os
import time

os.environ["CACTUS_TELEMETRY"] = "0"
os.environ["NEEDLE_TELEMETRY"] = "0"
os.environ["DO_NOT_TRACK"] = "1"

import cactus

calls_made = []


@cactus.tool
def get_weather(city: str):
    """Get the current weather for a city."""
    calls_made.append(city)
    return {"city": city, "temp_c": 27, "sky": "clear"}


print("=== Initializing Cactus/Needle ===")
t0 = time.perf_counter()
with cactus.Cactus(tools=[get_weather]) as agent:
    print(f"Agent loaded in {time.perf_counter() - t0:.2f}s")
    
    print("\n=== Testing agent.run() ===")
    t_run = time.perf_counter()
    run_out = agent.run("what's the weather in Lagos?")
    print(f"run() returned in {time.perf_counter() - t_run:.2f}s")
    print("run_out JSON:")
    print(json.dumps(run_out, indent=2, default=str))
    print("calls_made count after run():", len(calls_made))

    print("\n=== Testing agent.reset() ===")
    agent.reset()
    print("Reset OK")

    print("\n=== Testing agent.complete() ===")
    t_comp = time.perf_counter()
    comp_out = agent.complete("what's the weather in Lagos?")
    print(f"complete() returned in {time.perf_counter() - t_comp:.2f}s")
    print("comp_out JSON:")
    print(json.dumps(comp_out, indent=2, default=str))
    print("calls_made count after complete():", len(calls_made))

print("\nFinished successfully.")

