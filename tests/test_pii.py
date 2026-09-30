from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_email_with_plus_alias_and_trailing_punctuation() -> None:
    out = scrub_text("Contact first.last+tag@example.co.uk.")
    assert out == "Contact [REDACTED_EMAIL]."


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
        "+84901234567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd_without_matching_inside_longer_numbers() -> None:
    cccd = "079203012345"
    assert scrub_text(f"CCCD: {cccd}") == "CCCD: [REDACTED_CCCD]"
    longer_number = "10792030123456789012"
    assert scrub_text(longer_number) == longer_number


def test_scrub_payment_cards_with_common_lengths_and_separators() -> None:
    card_numbers = (
        "4222222222222",
        "378282246310005",
        "4111111111111111",
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4000000000000000006",
    )

    for card_number in card_numbers:
        assert scrub_text(f"Card: {card_number}") == "Card: [REDACTED_CREDIT_CARD]"

    longer_number = "40000000000000000006"
    assert scrub_text(longer_number) == longer_number
