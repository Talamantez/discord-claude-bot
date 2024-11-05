import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import os
from discord import Embed
import discord.ext.commands as commands
import datetime

from src.goals_bot import CompanyAssistant, GoalsDatabase

@pytest.fixture
def test_db():
    """Fixture for test database"""
    if os.path.exists("test_goals.json"):
        os.remove("test_goals.json")
    db = GoalsDatabase("test_goals.json")
    yield db
    if os.path.exists("test_goals.json"):
        os.remove("test_goals.json")

@pytest.fixture
async def bot(test_db):
    """Fixture for bot instance"""
    bot = CompanyAssistant()
    bot.db = test_db
    await bot.setup_hook()
    return bot

@pytest.fixture
def mock_ctx():
    """Fixture for Discord context"""
    ctx = AsyncMock()
    ctx.author.name = "TestUser"
    ctx.author.id = "123456789"
    ctx._testing = True  # Mark context as testing
    return ctx

@pytest.fixture
def mock_anthropic_response():
    """Fixture for Claude's response"""
    response = Mock()  # Changed from AsyncMock to Mock
    response.content = """1. Structured Objective:
    Increase revenue by 25% in Q1 2024

    2. Key Metrics:
    • Monthly revenue growth
    • Customer acquisition rate
    • Sales conversion rate

    3. Suggested Timeline:
    • Month 1: Market analysis
    • Month 2: Strategy implementation
    • Month 3: Review and adjust"""
    return response

class TestCompanyAssistant:
    @pytest.mark.asyncio
    async def test_set_objective(self, bot, mock_ctx, mock_anthropic_response):
        """Test setting a new objective"""
        # Create a regular mock instead of async mock
        def mock_create(*args, **kwargs):
            return mock_anthropic_response

        with patch.object(bot.anthropic.messages, 'create', side_effect=mock_create):  # Remove async mock
            command = bot.get_command('set_objective')
            assert command is not None

            try:
                await command.callback(mock_ctx, objective_text="Test objective")
            except Exception as e:
                pytest.fail(f"Command execution failed: {str(e)}")
                
    @pytest.mark.asyncio
    async def test_list_objectives_empty(self, bot, mock_ctx):
        """Test listing objectives when none exist"""
        command = bot.get_command('list')
        assert command is not None
        
        await command.callback(mock_ctx)
        mock_ctx.send.assert_called_once_with(
            "No objectives set yet! Use `!set_objective` to create one."
        )

    @pytest.mark.asyncio
    async def test_list_objectives_pagination(self, bot, mock_ctx):
        """Test pagination of objectives list"""
        # Add 5 objectives
        for i in range(5):
            bot.db.goals["objectives"][str(i+1)] = {
                "text": f"Test objective {i+1}",
                "created_by": "123456789",
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }

        command = bot.get_command('list')
        assert command is not None
        
        await command.callback(mock_ctx)
        
        # Should have called send twice (2 pages)
        assert mock_ctx.send.call_count == 2
        
        # Verify first page has 3 objectives
        first_page = mock_ctx.send.call_args_list[0][1]['embed']
        assert len(first_page.fields) == 3
        
        # Verify second page has 2 objectives
        second_page = mock_ctx.send.call_args_list[1][1]['embed']
        assert len(second_page.fields) == 2

    def test_clean_text(self, bot):
        """Test text cleaning functionality"""
        test_cases = [
            (
                "TextBlock(text='Test\\ntext')",
                "Test\ntext"
            ),
            (
                "[TextBlock(text='Multiple\\nlines')]",
                "Multiple\nlines"
            ),
            (
                "Normal text",
                "Normal text"
            )
        ]
        
        for input_text, expected in test_cases:
            assert bot.clean_text(input_text) == expected

    def test_format_section(self, bot):
        """Test section formatting"""
        input_text = """1. Structured Objective:
        Test objective

        2. Key Metrics:
        - Metric 1
        - Metric 2

        3. Suggested Timeline:
        - Month 1: Do thing
        - Month 2: Do other thing"""

        formatted = bot.format_section(input_text)
        
        # Check section headers
        assert "**1. Structured Objective**" in formatted
        assert "**2. Key Metrics**" in formatted
        assert "**3. Suggested Timeline**" in formatted
        
        # Check bullet point conversion
        assert "- Metric 1" not in formatted
        assert "- Metric 2" not in formatted
        assert "• Metric 1" in formatted
        assert "• Metric 2" in formatted
        assert "• Month 1: Do thing" in formatted
        assert "• Month 2: Do other thing" in formatted

@pytest.mark.asyncio
async def test_error_handling(bot, mock_ctx):
    """Test error handling in commands"""
    command = bot.get_command('set_objective')
    assert command is not None
    
    # Simulate an error in anthropic API
    with patch.object(bot.anthropic.messages, 'create', side_effect=Exception("API Error")):
        # Don't await the command directly, let it handle the error
        await command.callback(mock_ctx, objective_text="Test")
        
        # Check that send was called with an error embed
        mock_ctx.send.assert_called_once()
        error_embed = mock_ctx.send.call_args[1]['embed']
        assert isinstance(error_embed, Embed)
        assert error_embed.title == "❌ Error Setting Objective"
        assert "API Error" in error_embed.description

def test_env_variables():
    """Test environment variable handling"""
    with patch.dict(os.environ, {'DISCORD_TOKEN': '', 'ANTHROPIC_API_KEY': ''}):
        with pytest.raises(ValueError):
            CompanyAssistant()