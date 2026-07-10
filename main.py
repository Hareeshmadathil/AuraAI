from agents.video_downloader import download_video

print("=" * 50)
print("🚀 AuraAI Video Downloader")
print("=" * 50)

url = input("Paste YouTube URL: ")

try:
    filename = download_video(url)

    print("\n✅ Download completed!")
    print(f"Saved to: {filename}")

except Exception as e:
    print("\n❌ Error")
    print(e)