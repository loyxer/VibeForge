"""Design directions users can pick before generating a site.

The ids must match STYLES in frontend/src/components/StylePicker.tsx (a test
checks this); the text here is what the AI is told.
"""

STYLES: dict[str, str] = {
    "minimal": (
        "Minimal and airy: lots of whitespace, a restrained neutral palette "
        "with a single accent color, thin lines, crisp sans-serif type, no "
        "decorative clutter."
    ),
    "bold": (
        "Bold and colorful: saturated colors, huge chunky headlines, strong "
        "contrast, confident blocks of color, an energetic layout."
    ),
    "neon": (
        "Dark with neon: a near-black background, glowing neon accents "
        "(cyan, magenta, electric purple), subtle glows and gradients, a "
        "futuristic feel."
    ),
    "retro": (
        "Retro: a warm vintage palette (cream, mustard, burnt orange, teal), "
        "display fonts with a 70s/80s feel, subtle grain or halftone textures "
        "made with CSS, rounded badges."
    ),
    "elegant": (
        "Elegant and premium: refined serif headings, a muted luxurious "
        "palette (ivory, charcoal, gold or deep green), small caps with wide "
        "letter-spacing, calm and spacious."
    ),
    "playful": (
        "Playful and friendly: soft pastel colors, rounded shapes, bouncy "
        "hover effects, friendly rounded fonts, hand-drawn-feeling accents."
    ),
}
