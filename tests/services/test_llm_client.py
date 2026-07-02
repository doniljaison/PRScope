import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from app.services.llm_client import LLMClient, LLMParseError

@pytest.fixture
def llm_client():
    return LLMClient()

@pytest.mark.asyncio
async def test_analyze_diff_empty(llm_client):
    """Test that an empty diff returns an empty list immediately without calling API."""
    result = await llm_client.analyze_diff("")
    assert result == []

@pytest.mark.asyncio
async def test_analyze_diff_success(llm_client):
    """Test parsing a valid JSON response from Claude."""
    mock_response_content = '[{"path": "test.py", "line": 10, "body": "Typo here"}]'
    
    # We mock the entire Anthropic client's messages.create call
    with patch("app.services.llm_client.AsyncAnthropic") as mock_anthropic:
        # Setup the mock response chain
        mock_instance = mock_anthropic.return_value
        mock_create = AsyncMock()
        
        # Anthropic response structure: response.content[0].text
        class MockText:
            def __init__(self, text):
                self.text = text
                
        class MockContent:
            def __init__(self, text):
                self.content = [MockText(text)]
                
        mock_create.return_value = MockContent(mock_response_content)
        mock_instance.messages.create = mock_create
        
        # Override the client in our instance to use the mock
        llm_client.client = mock_instance
        
        result = await llm_client.analyze_diff("--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,2 @@\n-print('hello')\n+print('world')")
        
        assert len(result) == 1
        assert result[0]["path"] == "test.py"
        assert result[0]["body"] == "Typo here"
        mock_create.assert_called_once()

@pytest.mark.asyncio
async def test_analyze_diff_markdown_stripping(llm_client):
    """Test stripping ```json blocks from the LLM response."""
    mock_response_content = '```json\n[{"path": "test.py", "line": 10, "body": "Typo here"}]\n```'
    
    with patch("app.services.llm_client.AsyncAnthropic") as mock_anthropic:
        mock_instance = mock_anthropic.return_value
        mock_create = AsyncMock()
        
        class MockText:
            def __init__(self, text):
                self.text = text
                
        class MockContent:
            def __init__(self, text):
                self.content = [MockText(text)]
                
        mock_create.return_value = MockContent(mock_response_content)
        mock_instance.messages.create = mock_create
        llm_client.client = mock_instance
        
        result = await llm_client.analyze_diff("diff content")
        
        assert len(result) == 1
        assert result[0]["path"] == "test.py"

@pytest.mark.asyncio
async def test_analyze_diff_invalid_json(llm_client):
    """Test that invalid JSON raises LLMParseError."""
    mock_response_content = 'This is not JSON'
    
    with patch("app.services.llm_client.AsyncAnthropic") as mock_anthropic:
        mock_instance = mock_anthropic.return_value
        mock_create = AsyncMock()
        
        class MockText:
            def __init__(self, text):
                self.text = text
                
        class MockContent:
            def __init__(self, text):
                self.content = [MockText(text)]
                
        mock_create.return_value = MockContent(mock_response_content)
        mock_instance.messages.create = mock_create
        llm_client.client = mock_instance
        
        with pytest.raises(LLMParseError):
            await llm_client.analyze_diff("diff content")
