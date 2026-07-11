from services.pipeline import process_video


def main() -> None:
    print("=" * 55)
    print("AURA AI — Content Processing Pipeline")
    print("=" * 55)

    url = input("Paste an authorized YouTube URL: ")

    try:
        video_path, audio_path, transcript_path = process_video(url)

    except ValueError as error:
        print(f"\nInput error: {error}")

    except KeyboardInterrupt:
        print("\nOperation cancelled by the user.")

    except Exception as error:
        print("\nAn error occurred:")
        print(error)

    else:
        print("\n" + "=" * 55)
        print("Processing completed successfully.")
        print(f"Video: {video_path}")
        print(f"Audio: {audio_path}")
        print(f"Transcript: {transcript_path}")
        print("=" * 55)


if __name__ == "__main__":
    main()