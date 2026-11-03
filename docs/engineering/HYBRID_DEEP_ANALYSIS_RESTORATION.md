# Hybrid Deep Analysis Restoration

The final VisionQC 2.0 build now restores the intended Deep Analysis flow:

1. Run the deterministic local OpenCV/rule engine.
2. Preserve and display all local metrics even when cloud AI is unavailable.
3. Automatically send the same image plus local measurements to Gemini when `GEMINI_API_KEY` is configured.
4. Display Gemini findings in a dedicated tab.
5. Export one combined JSON document containing both result sets.

Configuration:

```env
GEMINI_API_KEY=your_key
```

The cloud failure path is fail-safe: it never removes or invalidates the completed local analysis.


Video Temporal Analysis also performs an automatic Gemini review using a representative sampled frame plus the complete local timeline context.
