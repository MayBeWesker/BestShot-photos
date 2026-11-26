# Poetry Recommendations

The sidebar below **Regenerate** offers optional verse recommendations for the current photo story. Users can add a mood, request up to three suggestions, inspect the source edition, copy a verse with attribution, or copy it together with their caption.

## Matching and authenticity

The local backend sends only the currently selected photos (up to nine compressed thumbnails), the current caption (up to 500 characters), saved story context, the most recent revision request, and an optional mood (up to 300 characters) to the configured vision API. The model is instructed to match both visible imagery and emotional intent and to return no suggestions when none fit. Semantic suitability is still a model judgment.

The initial catalog contains 17 excerpts from Tang and Song works, checked against the linked Wikisource editions on November 26, 2026. Original verse is transcribed in simplified Chinese with modern punctuation. Each entry includes a fixed source revision, author, title, and era. Only the original public-domain verse is transcribed, not source editorial notes.

The model returns catalog IDs, matching reasons, and photo positions. The backend supplies the quoted words, author, title, and source from the catalog; model-provided replacements for these fields are ignored. Unknown IDs and invalid positions are rejected. No invented verse is used as a fallback. This limited catalog favors traceable attribution over open-ended quotation; additional historical works can be added after checking their source editions.

Changing the selected photos, their order, or the generated caption clears the visible suggestions. Each request uses a bounded current snapshot rather than an accumulating conversation history. Requests in progress cannot populate a newer story with stale results.
