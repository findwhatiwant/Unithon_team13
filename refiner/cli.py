import argparse
import os
import sys

from refiner.llm import GeminiClient
from refiner.models import Mode, RefineRequest, Tone
from refiner.pipeline import Pipeline


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="refine",
        description="LLM 기반 메시지 다듬기 파이프라인",
    )
    parser.add_argument("text", help="다듬을 메시지")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        default=Mode.POLISH.value,
        help="polish(교정) / tone(톤 변환) / summarize(요약)",
    )
    parser.add_argument(
        "--tone",
        choices=[tone.value for tone in Tone],
        default=None,
        help="formal / casual / business / friendly (mode=tone일 때 필수)",
    )
    parser.add_argument("--context", default=None, help="받는 사람·상황 설명")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 없습니다. .env 파일 또는 환경변수에 설정하세요.", file=sys.stderr)
        return 1

    request = RefineRequest(
        text=args.text,
        mode=Mode(args.mode),
        tone=Tone(args.tone) if args.tone else None,
        context=args.context,
    )
    result = Pipeline(GeminiClient(api_key)).run(request)
    if not result.success:
        print(f"실패: {result.error}", file=sys.stderr)
        return 1

    print(result.refined_text)
    if result.changes:
        print("\n변경 사항:")
        for change in result.changes:
            print(f"- {change}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
