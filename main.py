import json
from pathlib import Path
from typing import Any

from services.pipeline import process_video


def load_generated_content(content_path: Path) -> dict[str, Any]:
    """
    Load the generated creator content from its JSON file.
    """

    if not content_path.exists():
        raise FileNotFoundError(
            f"Generated content file not found: {content_path}"
        )

    try:
        return json.loads(
            content_path.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Generated content file contains invalid JSON: {content_path}"
        ) from error


def main() -> None:
    print("=" * 60)
    print("AURA AI - Content Processing Pipeline")
    print("=" * 60)

    url = input("Paste an authorized YouTube URL: ").strip()

    try:
        (
            video_path,
            audio_path,
            transcript_path,
            timestamp_path,
            analysis,
            analysis_path,
            content_path,
        ) = process_video(url)

        generated_content = load_generated_content(content_path)

    except ValueError as error:
        print(f"\nInput error: {error}")

    except KeyboardInterrupt:
        print("\nOperation cancelled by the user.")

    except Exception as error:
        print("\nAn error occurred:")
        print(error)

    else:
        print("\n" + "=" * 60)
        print("Processing completed successfully.")
        print("=" * 60)

        print("\nGenerated files")
        print("-" * 60)
        print(f"Video       : {video_path}")
        print(f"Audio       : {audio_path}")
        print(f"Transcript  : {transcript_path}")
        print(f"Timestamps  : {timestamp_path}")
        print(f"Analysis    : {analysis_path}")
        print(f"AI content  : {content_path}")

        print("\nTranscript details")
        print("-" * 60)
        print(f"Words       : {analysis.get('word_count', 0)}")
        print(f"Characters  : {analysis.get('character_count', 0)}")
        print(f"Language    : {analysis.get('language', 'Unknown')}")
        print(f"Sentiment   : {analysis.get('sentiment', 'Unknown')}")
        print(f"Viral score : {analysis.get('viral_score', 0)}")

        keywords = analysis.get("keywords", [])

        if keywords:
            print(f"Keywords    : {', '.join(keywords)}")
        else:
            print("Keywords    : None")

        print("\nSummary")
        print("-" * 60)
        print(analysis.get("summary", "No summary generated."))

        clip_candidates = analysis.get("clip_candidates", [])

        print("\nClip candidates")
        print("-" * 60)

        if clip_candidates:
            for index, candidate in enumerate(
                clip_candidates,
                start=1,
            ):
                quote = candidate.get("quote", "")
                reason = candidate.get("reason", "")

                print(f"\nCandidate {index}")
                print(f"Quote  : {quote}")
                print(f"Reason : {reason}")
        else:
            print("No clip candidates found.")

        print("\nGenerated creator content")
        print("-" * 60)

        print(
            "\nYouTube title:\n"
            f"{generated_content.get('youtube_title', 'No title generated.')}"
        )

        print(
            "\nYouTube description:\n"
            f"{generated_content.get('youtube_description', 'No description generated.')}"
        )

        print(
            "\nInstagram caption:\n"
            f"{generated_content.get('instagram_caption', 'No Instagram caption generated.')}"
        )

        print(
            "\nX post:\n"
            f"{generated_content.get('twitter_post', 'No X post generated.')}"
        )

        print(
            "\nLinkedIn post:\n"
            f"{generated_content.get('linkedin_post', 'No LinkedIn post generated.')}"
        )

        hashtags = generated_content.get("hashtags", [])
        youtube_tags = generated_content.get("youtube_tags", [])
        shorts_titles = generated_content.get("shorts_titles", [])

        print("\nHashtags")
        print("-" * 60)
        print(
            " ".join(hashtags)
            if hashtags
            else "No hashtags generated."
        )

        print("\nYouTube tags")
        print("-" * 60)
        print(
            ", ".join(youtube_tags)
            if youtube_tags
            else "No YouTube tags generated."
        )

        print("\nShorts titles")
        print("-" * 60)

        if shorts_titles:
            for index, title in enumerate(shorts_titles, start=1):
                print(f"{index}. {title}")
        else:
            print("No Shorts titles generated.")

        print("\nTranscript preview")
        print("-" * 60)
        print(
            analysis.get(
                "preview",
                "No transcript preview available.",
            )
        )

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()