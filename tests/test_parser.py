"""Tests for CaptainHook parser."""

import pytest
from captainhook.parser import (
    ParseError,
    Tag,
    TagType,
    parse_tag,
    parse_all,
    is_valid_tag,
    parse_container_tags, parse_cheatcodes, parse_self_closing
)


class TestParser:
    """Test tag parsing."""
    
    def test_parse_self_closing(self):
        """Test parsing [action /] tags."""
        tag = parse_tag("[hello /]")
        assert tag.tag_type == TagType.SINGLE
        assert tag.action == "hello"
        assert tag.namespace is None
    
    def test_parse_cheatcode(self):
        """Test parsing [ns:action params /] cheatcodes."""
        tag = parse_tag("[browser:navigate https://example.com /]")
        assert tag.tag_type == TagType.CHEATCODE
        assert tag.namespace == "browser"
        assert tag.action == "navigate"
        assert "https://example.com" in tag.params
    
    def test_parse_container(self):
        """Test parsing [tag]content[/tag] containers."""
        tag = parse_tag("[echo]Hello World[/echo]")
        assert tag.tag_type == TagType.DOUBLE
        assert tag.action == "echo"
        assert tag.content == "Hello World"
    
    def test_parse_cheatcode_with_attributes(self):
        """Test cheatcode with key=value attributes."""
        tag = parse_tag('[tool:run command="ls" timeout="30" /]')
        assert tag.tag_type == TagType.CHEATCODE
        assert tag.namespace == "tool"
        assert tag.action == "run"
        assert tag.attributes["command"] == "ls"
        assert tag.attributes["timeout"] == "30"

    def test_parse_escaped_attribute_value(self):
        tag = parse_tag('[tool:run command="say \\"hello\\"" /]')
        assert tag.attributes["command"] == 'say "hello"'
    
    def test_parse_all_multiple_tags(self):
        """Test parsing multiple tags from text."""
        text = """
        [hello /]
        [math:add 5 3 /]
        [echo]Content here[/echo]
        """
        tags = parse_all(text)
        
        assert len(tags) == 3
        assert tags[0].action == "hello"
        assert tags[1].namespace == "math"
        assert tags[2].tag_type == TagType.DOUBLE
    
    def test_is_valid_tag(self):
        """Test tag validation."""
        assert is_valid_tag("[hello /]") is True
        assert is_valid_tag("[browser:navigate url /]") is True
        assert is_valid_tag("[echo]content[/echo]") is True
        assert is_valid_tag("not a tag") is False
        assert is_valid_tag("[incomplete") is False

    def test_parse_tag_rejects_malformed(self):
        """Malformed markup should fail closed."""
        with pytest.raises(ParseError):
            parse_tag("[mission]unclosed")

    def test_container_payload_remains_data(self):
        """Nested control-like payload should stay content by default."""
        tags = parse_all("[mission]Draft this from [agent_tools:run x=1 /][/mission]")
        assert len(tags) == 1
        assert tags[0].tag_type == TagType.DOUBLE
        assert tags[0].action == "mission"
        assert "[agent_tools:run" in tags[0].raw


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
