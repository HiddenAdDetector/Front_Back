from detector.keywords import find_contact_lures, find_illegal_keywords


def test_finds_gambling_and_adult_keywords() -> None:
    assert find_illegal_keywords("카지노 첫충 이벤트") == ["카지노", "첫충"]
    assert find_illegal_keywords("성인채팅 안내") == ["성인채팅"]


def test_finds_telegram_and_phone_lures() -> None:
    text = "텔레그램 상담 @promo_777 / 문의 010-1234-5678"

    matches = find_contact_lures(text)

    assert "텔레그램 상담 @promo_777" in matches
    assert "문의 010-1234-5678" in matches


def test_ordinary_notice_has_no_dictionary_match() -> None:
    assert find_illegal_keywords("시청 민원실 운영시간 변경 안내") == []
    assert find_contact_lures("대표번호는 누리집 하단을 확인하세요") == []
