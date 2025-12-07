import pytest
from improved_auto_reply import extract_business_email

def test_strict_line():
    body = "Hello\nBusiness email - contact@example.com\nThanks"
    assert extract_business_email(body) == "contact@example.com"

def test_colon_separator():
    body = "Business email:  user@example.org"
    assert extract_business_email(body) == "user@example.org"

def test_next_line():
    body = "Please contact:\nBusiness email\ncontact2@example.net"
    assert extract_business_email(body) == "contact2@example.net"

def test_none():
    body = "No contact here"
    assert extract_business_email(body) is None
