# Local voice selection

AuraAI lists enabled Windows System.Speech voices without installing anything.
Only safe metadata—name, culture, gender metadata, and availability—is shown.
The adapter does not clone or imitate people and does not call a network API.

Create a 20–30 second audition after choosing an installed voice. The audition
uses the revised opening, deterministic normalization, pronunciation overrides,
and transient text files that are removed after synthesis. Full narration is
section-chunked and joined as compatible PCM WAV data to limit memory use.

If System.Speech or the selected voice is unavailable, AuraAI reports a blocked
result and creates no fake narration.
