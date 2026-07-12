from services.pipeline import process_video


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
            clip_candidates,
        ) = process_video(url)

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

        print(f"\nVideo       : {video_path}")
        print(f"Audio       : {audio_path}")
        print(f"Transcript  : {transcript_path}")
        print(f"Timestamps  : {timestamp_path}")
        print(f"Analysis    : {analysis_path}")
        print(f"Content     : {content_path}")

        print("\nAnalysis")
        print("-" * 60)
        print(f"Summary     : {analysis.get('summary', '')}")
        print(f"Language    : {analysis.get('language', '')}")
        print(f"Sentiment   : {analysis.get('sentiment', '')}")
        print(f"Viral Score : {analysis.get('viral_score', '')}")

        print("\nKeywords")
        print("-" * 60)

        keywords = analysis.get("keywords", [])

        if keywords:
            print(", ".join(keywords))
        else:
            print("No keywords found.")

        print("\nTimestamped Clip Candidates")
        print("-" * 60)

        if clip_candidates:
            for index, clip in enumerate(
                clip_candidates,
                start=1,
            ):
                print(f"\nCandidate {index}")
                print(f"Quote      : {clip['quote']}")
                print(f"Reason     : {clip['reason']}")
                print(f"Start      : {clip['start']} sec")
                print(f"End        : {clip['end']} sec")
                print(f"Duration   : {clip['duration']} sec")
                print(f"Confidence : {clip['confidence']}")
        else:
            print("No timestamped clip candidates found.")

        print("\nTranscript Preview")
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