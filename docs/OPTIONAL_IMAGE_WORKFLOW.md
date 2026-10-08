# Optional: attach an illustration with Claude Code

Related: [USAGE](USAGE.md), [LIMITATIONS](LIMITATIONS.md).

This is **not part of the pipeline**. It is a manual workflow that exists only
if you use Claude Code with the Chrome extension, and it ends with a human
clicking Post. It was built and tested against Gemini's image model; the
workflow below was not re-run for this documentation pass.

## What it does

With Claude Code's browser-control tools connected to your Chrome, you can ask
it to open an image model in one tab, generate an illustration from a prompt,
open X's compose window in another tab, paste the post, paste the image, and
stop, leaving a prepared tweet that only needs reading and a click.

## Why it cannot be automated

- **Browser-control tools are unavailable in headless mode.** A `claude -p`
  process (what a cron job runs) cannot use them, even when allowed. They exist
  only in an interactive session with the extension connected.
- **X's compose link accepts text only.** Attaching a file through a URL is
  refused on their side, deliberately. Feeding a server file through a
  browser's file-upload tool is refused for the same reason.

The legitimate path is the clipboard: copy the image in one tab, paste it in
the other. Both tabs are your own logged-in sessions.

## Prerequisites

- Claude Code with the Chrome extension, connected to the Google account you
  use for the image model and the X account you post from.
- An image model you can drive by typing a prompt and clicking "copy image".
- Patience for the first run, which finds button positions and click order.

## Steps

1. **Draft the image prompt** from what the post is about. A concrete scene
   beats an abstract concept. For a consistent series look, describe a grammar
   (viewpoint, palette, composition) rather than naming an illustrator: models
   apply a caricature of the artist's signature instead of drawing the scene.
2. **Generate, then wait.** 20 to 40 seconds is normal; a screenshot taken too
   early shows the prompt still in the input box, which is not a failure.
3. **Copy the image** with the model's own copy button, not a screenshot or
   "save as".
4. **Open X's compose window**, click into the text field, paste the post, then
   paste the image (`Ctrl+V` / `Cmd+V`). Scroll to confirm the thumbnail
   attached ("Edit" and "Add description" appear under it).
5. **Stop there.** The last click is a human's, on purpose.

## Traps

- A prompt that included its own instructional label ("IMAGE PROMPT, paste as
  is") got the label drawn into the picture. Keep instructions for a human in a
  separate message from anything that will be pasted verbatim.
- On a brand-new chat with an image model, Return sometimes inserts a newline
  because the input is multiline: click the send arrow.
- The upload widget refuses a path from your disk or server: correct behaviour,
  use the clipboard path.
