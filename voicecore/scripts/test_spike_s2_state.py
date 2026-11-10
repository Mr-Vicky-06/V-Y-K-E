import json
import os
import cactus

@cactus.tool
def get_weather(city: str):
    """Get the current weather for a city."""
    return {"city": city, "temp_c": 27}

# Test 1: stateful conversation turn 1 then turn 2
print("=== Stateful Agent ===")
with cactus.Cactus(tools=[get_weather]) as agent:
    out1 = agent.complete("what is the weather in Paris?")
    print("Turn 1 calls:", [c["name"] for c in out1.get("function_calls", [])])
    out2 = agent.complete("and what about London?")
    print("Turn 2 calls:", out2.get("function_calls", []))
    agent.reset()
    out3 = agent.complete("and what about London?")
    print("Turn 3 after reset calls:", out3.get("function_calls", []))

# Test 2: stateless=True
print("\n=== Stateless Agent ===")
with cactus.Cactus(tools=[get_weather], stateless=True) as agent_sl:
    out_sl1 = agent_sl.complete("what is the weather in Paris?")
    print("Stateless 1:", [c["name"] for c in out_sl1.get("function_calls", [])])
    out_sl2 = agent_sl.complete("and what about London?")
    print("Stateless 2:", out_sl2.get("function_calls", []))

