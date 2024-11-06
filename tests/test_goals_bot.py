import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import os
from discord import Embed
import discord.ext.commands as commands
import datetime
from discord import Color
from asyncio import TimeoutError
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
    response = Mock()
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
    """Test basic bot functionality"""
    
    @pytest.mark.asyncio
    async def test_set_objective(self, bot, mock_ctx, mock_anthropic_response):
        """Test setting a new objective"""
        def mock_create(*args, **kwargs):
            return mock_anthropic_response

        with patch.object(bot.anthropic.messages, 'create', side_effect=mock_create):
            command = bot.get_command('set_objective')
            assert command is not None
            await command.callback(mock_ctx, objective_text="Test objective")
            
            # Verify database update
            assert len(bot.db.goals["objectives"]) == 1
            assert "1" in bot.db.goals["objectives"]
            
            # Verify embed
            assert mock_ctx.send.called
            called_embed = mock_ctx.send.call_args[1]['embed']
            assert called_embed.title == "📋 New Objective Created"
           
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
        
        assert mock_ctx.send.call_count == 2
        first_page = mock_ctx.send.call_args_list[0][1]['embed']
        assert len(first_page.fields) == 3
        second_page = mock_ctx.send.call_args_list[1][1]['embed']
        assert len(second_page.fields) == 2

    def test_clean_text(self, bot):
        """Test text cleaning functionality"""
        test_cases = [
            ("TextBlock(text='Test\\ntext')", "Test\ntext"),
            ("[TextBlock(text='Multiple\\nlines')]", "Multiple\nlines"),
            ("Normal text", "Normal text")
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
        
        assert "**1. Structured Objective**" in formatted
        assert "**2. Key Metrics**" in formatted
        assert "**3. Suggested Timeline**" in formatted
        assert "• Metric 1" in formatted
        assert "• Metric 2" in formatted

@pytest.mark.asyncio
class TestObjectiveCRUD:
    @pytest.mark.asyncio
    async def test_reset_railway(self, bot, mock_ctx):
        """Test resetting the database file"""
        # Setup: Add some test data and mock admin permissions
        mock_ctx.author.guild_permissions.administrator = True
        
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        command = bot.get_command('reset_railway')
        await command.callback(mock_ctx)
        
        # Verify database was reset
        assert os.path.exists(bot.db.filename)
        assert bot.db.goals == {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        
        # Verify success message
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert called_embed.title == "🔄 Database Reset"
        assert called_embed.color == Color.green()
        
    async def test_add_progress(self, bot, mock_ctx):
        """Test adding progress updates"""
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        command = bot.get_command('add_progress')
        update_text = "Made progress on objective"
        await command.callback(mock_ctx, objective_id="1", update_text=update_text)
        
        # Database assertions
        assert len(bot.db.goals["updates"]) == 1
        assert bot.db.goals["updates"][0]["objective_id"] == "1"
        assert bot.db.goals["updates"][0]["text"] == update_text
        
        # Embed assertions
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert called_embed.title == "📝 Progress Update Added"
        assert called_embed.description == "Update added to Objective 1"
        assert called_embed.color == Color.green()
        assert len(called_embed.fields) == 1
        assert called_embed.fields[0].name == "Update"
        assert called_embed.fields[0].value == update_text

    async def test_view_progress(self, bot, mock_ctx):
        """Test viewing progress updates"""
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        updates = [f"Update {i}" for i in range(6)]
        
        for update in updates:
            bot.db.goals["updates"].append({
                "objective_id": "1",
                "text": update,
                "updated_by": "123456789",
                "updated_at": str(datetime.datetime.now())
            })
            
        command = bot.get_command('view_progress')
        await command.callback(mock_ctx, objective_id="1")
        
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert len(called_embed.fields) == 5
        for i, update in enumerate(updates[-5:]):
            assert update in called_embed.fields[i].value

    async def test_update_status(self, bot, mock_ctx):
        """Test updating objective status"""
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        command = bot.get_command('update_status')
        
        # Test valid status update
        await command.callback(mock_ctx, objective_id="1", status="completed")
        assert bot.db.goals["objectives"]["1"]["status"] == "completed"
        
        # Test invalid status
        mock_ctx.reset_mock()
        await command.callback(mock_ctx, objective_id="1", status="invalid")
        mock_ctx.send.assert_called_with(
            "Invalid status. Please use one of: active, completed, cancelled"
        )

    async def test_delete_objective(self, bot, mock_ctx):
        """Test deleting objectives"""
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        command = bot.get_command('delete_objective')
        await command.callback(mock_ctx, objective_id="1")
        
        assert "1" not in bot.db.goals["objectives"]
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert called_embed.title == "🗑️ Objective Deleted"


    @pytest.mark.asyncio
    async def test_clear_all(self, bot, mock_ctx):
        """Test clearing all objectives"""
        # Setup: Add some test data
        bot.db.goals["objectives"]["1"] = {
            "text": "Test objective 1",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        bot.db.goals["updates"].append({
            "objective_id": "1",
            "text": "Test update",
            "updated_by": "123456789",
            "updated_at": str(datetime.datetime.now())
        })
        
        # Mock admin permissions
        mock_ctx.author.guild_permissions.administrator = True
        
        # Mock the reaction check
        confirm_msg = AsyncMock()
        mock_ctx.send.return_value = confirm_msg
        
        # Create a mock reaction and user
        mock_reaction = AsyncMock()
        mock_reaction.emoji = "✅"
        mock_user = mock_ctx.author
        
        # Mock wait_for to simulate reaction
        bot.wait_for = AsyncMock(return_value=(mock_reaction, mock_user))
        
        command = bot.get_command('clear_all')
        await command.callback(mock_ctx)
        
        # Verify database was cleared
        assert len(bot.db.goals["objectives"]) == 0
        assert len(bot.db.goals["updates"]) == 0
        assert len(bot.db.goals["metrics"]) == 0
        
        # Verify confirmation message was sent
        mock_ctx.send.assert_any_call("⚠️ **WARNING**: This will delete ALL objectives and updates. React with ✅ to confirm.")
        
        # Verify success embed was sent
        called_embed = mock_ctx.send.call_args_list[-1][1]['embed']
        assert called_embed.title == "💥 Database Cleared"
        assert called_embed.color == Color.red()

    @pytest.mark.asyncio
    async def test_clear_all_no_permission(self, bot, mock_ctx):
        """Test clear_all without admin permissions"""
        mock_ctx.author.guild_permissions.administrator = False
        
        # Test permission check directly
        has_permission = await bot._check_admin_permission(mock_ctx)
        assert not has_permission
        mock_ctx.send.assert_called_once_with("❌ Only administrators can use this command!")
        
    @pytest.mark.asyncio
    async def test_clear_all_timeout(self, bot, mock_ctx):
        """Test clear_all when confirmation times out"""
        # Mock admin permissions
        mock_ctx.author.guild_permissions.administrator = True
        
        # Mock the confirmation message
        confirm_msg = AsyncMock()
        mock_ctx.send.return_value = confirm_msg
        
        # Mock wait_for to simulate timeout
        bot.wait_for = AsyncMock(side_effect=TimeoutError())
        
        command = bot.get_command('clear_all')
        await command.callback(mock_ctx)
        
        # Verify timeout message
        mock_ctx.send.assert_called_with("Clear all operation cancelled (timed out)")
        
        # Verify database wasn't cleared
        assert bot.db.goals == bot.db.load_goals()


@pytest.mark.asyncio
async def test_error_handling(bot, mock_ctx):
    """Test error handling in commands"""
    command = bot.get_command('set_objective')
    assert command is not None
    
    with patch.object(bot.anthropic.messages, 'create', side_effect=Exception("API Error")):
        await command.callback(mock_ctx, objective_text="Test")
        
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