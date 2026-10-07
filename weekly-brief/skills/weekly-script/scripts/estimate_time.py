"""Estimate a Korean narration's duration; stdin must contain spoken text only."""
import json
import sys


def estimate(text):
    count = sum(char.isalnum() for char in text)
    if not count:
        raise ValueError('낭독 본문이 비어 있습니다.')
    # ponytail: 발음으로 풀어 쓴 글자 수의 근사값; 실측 리허설로 개인 속도 보정.
    return count, round(count / 330 * 60 + 15, 1), round(count / 300 * 60 + 20, 1)


if __name__ == '__main__':
    try:
        count, target, slow = estimate(sys.stdin.read())
    except ValueError as error:
        sys.exit(str(error))
    print(json.dumps({
        'spoken_characters': count,
        'estimated_seconds': target,
        'slow_seconds': slow,
        'needs_shortening': slow > 180,
    }, ensure_ascii=False))
