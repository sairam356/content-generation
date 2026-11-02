# Using Claude Desktop (instead of Claude Code)

Claude Code is the recommended route because it can read your project files and run `higgsfield`/`ffmpeg`.
If you prefer the Claude Desktop app:

1. Claude Desktop -> Settings -> Connectors -> **Add custom connector**
   - Name: `Higgsfield`   URL: `https://mcp.higgsfield.ai/mcp` -> Connect -> sign in to Higgsfield.
2. Start a new chat, enable the Higgsfield connector (+ -> Connectors).
3. Attach `projects/<p>/brief.json` and the `projects/<p>/audio/*.wav` files, plus 5-20 photos of you
   (or tell Claude the Soul ID you already trained).
4. Paste the contents of `projects/<p>/claude_prompt.md`.
5. Download every clip Claude returns into `projects/<p>/clips/scene_<id>.mp4` (and `clips/cta.mp4`), then run
   `python -m pipeline assemble projects/<p>` in PowerShell to get `final.mp4` with Telugu captions.
