from pathlib import Path

from app.parsers.amass import parse_amass_output

TXT_FIXTURE = Path(__file__).parent / "fixtures" / "amass_sample.txt"
JSONL_FIXTURE = Path(__file__).parent / "fixtures" / "subfinder_sample.jsonl"


def test_parses_plain_text_deduplicated():
    result = parse_amass_output(TXT_FIXTURE)
    # 5 lines in fixture, "dev.client.com" appears twice
    names = [a.name for a in result.assets]
    assert len(names) == 4
    assert names.count("dev.client.com") == 1


def test_classifies_domain_vs_subdomain():
    result = parse_amass_output(TXT_FIXTURE)
    by_name = {a.name: a for a in result.assets}
    assert by_name["client.com"].asset_type == "domain"
    assert by_name["dev.client.com"].asset_type == "subdomain"


def test_parses_subfinder_jsonl_host_field():
    result = parse_amass_output(JSONL_FIXTURE)
    names = {a.name for a in result.assets}
    assert names == {"dev.client.com", "mail.client.com"}  # duplicate deduped


def test_lowercases_and_strips_trailing_dot():
    result = parse_amass_output("Dev.Client.com.\n")
    assert result.assets[0].name == "dev.client.com"


def test_blank_lines_are_ignored():
    result = parse_amass_output("client.com\n\n\napi.client.com\n")
    assert len(result.assets) == 2
