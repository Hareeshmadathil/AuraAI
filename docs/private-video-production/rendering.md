# Local rendering

FFmpeg and FFprobe are detected at runtime and are never bundled or installed.
Commands are argument lists executed with `shell=False`, bounded timeouts, safe
output roots, and sanitized summaries. The 720p option is an explicitly marked
internal placeholder preview. The 1080p option requires all founder assets.

The draft uses H.264 video, AAC audio, MP4, `yuv420p`, 30 fps, and web fast
start. It is watermarked `INTERNAL REVIEW — NOT FOR PUBLICATION`; the filename
contains `PRIVATE_DRAFT`, never `final`.

FFprobe verification checks file size, video and audio streams, codecs,
resolution, duration tolerance, and SHA-256. FFmpeg exit code alone is not
considered successful verification.
