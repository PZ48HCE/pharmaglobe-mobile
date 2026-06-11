import json

transcript_path = "/Users/upadhayaysandesh/.gemini/antigravity/brain/11e3033f-54f9-47f6-ab62-cdc800a0811e/.system_generated/logs/transcript.jsonl"

print("Searching transcript for steps 1760-1830...")
with open(transcript_path, "r") as f:
    for line in f:
        try:
            d = json.loads(line)
        except Exception:
            continue
        step_idx = d.get("step_index", 0)
        if 1760 <= step_idx <= 1830:
            print(f"\nStep {step_idx} (type={d.get('type')}, source={d.get('source')}, status={d.get('status')}):")
            content = d.get("content", "")
            if content:
                print(content[:800] + ("..." if len(content) > 800 else ""))
            if "tool_calls" in d:
                print(d["tool_calls"])
