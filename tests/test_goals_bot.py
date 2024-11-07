import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import os
from discord import Embed
commands = pytest.importorskip("discord.ext.commands")
import datetime
from discord import Color
from asyncio import TimeoutError
from src.goals_bot import CompanyAssistant, GoalsDatabase

@pytest.fixture
def test_db():
    """Fixture for test database"""
    db = GoalsDatabase("test_goals")
    yield db
    # Clean up all test files after tests
    for filename in os.listdir('.'):
        if filename.startswith('test_goals_') and filename.endswith('.json'):
            os.remove(filename)

@pytest.fixture
def test_server_id():
    """Fixture for test server ID"""
    return "123456789"

@pytest.fixture
def second_server_id():
    """Fixture for second test server ID"""
    return "987654321"

@pytest.fixture
async def bot(test_db):
    """Fixture for bot instance"""
    bot = CompanyAssistant()
    bot.db = test_db
    await bot.setup_hook()
    return bot

@pytest.fixture
def mock_ctx(test_server_id):
    """Fixture for Discord context"""
    ctx = AsyncMock()
    ctx.author.name = "TestUser"
    ctx.author.id = "123456789"
    ctx.guild.id = test_server_id
    ctx._testing = True
    return ctx

@pytest.fixture
def mock_ctx_second_server(second_server_id):
    """Fixture for Discord context in second server"""
    ctx = AsyncMock()
    ctx.author.name = "TestUser2"
    ctx.author.id = "987654321"
    ctx.guild.id = second_server_id
    ctx._testing = True
    return ctx

@pytest.fixture
def mock_anthropic_response():
    """Fixture for Claude's response"""
    response = AsyncMock()
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
        server_id = str(mock_ctx.guild.id)
        
        # Create mock messages instance
        mock_messages = Mock()
        mock_messages.create = Mock(return_value=mock_anthropic_response)
        bot.anthropic.messages = mock_messages
        
        command = bot.get_command('set_objective')
        assert command is not None
        await command.callback(mock_ctx, objective_text="Test objective")
        
        # Verify database update
        server_goals = bot.db.get_goals(server_id)
        assert len(server_goals["objectives"]) == 1
        assert "1" in server_goals["objectives"]
          
    @pytest.mark.asyncio
    async def test_list_objectives_empty(self, bot, mock_ctx):
        """Test listing objectives when none exist"""
        server_id = str(mock_ctx.guild.id)
        
        command = bot.get_command('list')
        assert command is not None
        await command.callback(mock_ctx)
        
        mock_ctx.send.assert_called_once_with(
            "No objectives set yet! Use `!set_objective` to create one."
        )

    @pytest.mark.asyncio
    async def test_list_objectives_single_page(self, bot, mock_ctx):
        """Test listing objectives that fit on one page"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Add two objectives
        for i in range(2):
            server_goals["objectives"][str(i+1)] = {
                "text": f"Test objective {i+1}",
                "created_by": "123456789",
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
        bot.db.save_goals(server_id)
        
        command = bot.get_command('list')
        await command.callback(mock_ctx)
        
        # Verify single embed was sent
        assert mock_ctx.send.call_count == 1
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert called_embed.title == "📊 Company Objectives"
        assert len(called_embed.fields) == 2

    @pytest.mark.asyncio
    async def test_list_objectives_pagination(self, bot, mock_ctx):
        """Test pagination of objectives list"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Add 5 objectives to force pagination
        for i in range(5):
            server_goals["objectives"][str(i+1)] = {
                "text": f"Test objective {i+1}\n" * 5,  # Make text longer to test formatting
                "created_by": "123456789",
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
        bot.db.save_goals(server_id)
        
        command = bot.get_command('list')
        await command.callback(mock_ctx)
        
        # Verify pagination
        assert mock_ctx.send.call_count == 2
        first_page = mock_ctx.send.call_args_list[0][1]['embed']
        assert len(first_page.fields) == 3
        assert first_page.title == "📊 Company Objectives"
        
        second_page = mock_ctx.send.call_args_list[1][1]['embed']
        assert len(second_page.fields) == 2
        assert second_page.title == "📊 Company Objectives (Page 2)"

    @pytest.mark.asyncio
    async def test_list_objectives_with_status(self, bot, mock_ctx):
        """Test listing objectives with different statuses"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Add objectives with different statuses
        statuses = ["active", "completed", "cancelled"]
        for i, status in enumerate(statuses, 1):
            server_goals["objectives"][str(i)] = {
                "text": f"Test objective {i}",
                "created_by": "123456789",
                "created_at": str(datetime.datetime.now()),
                "status": status
            }
        bot.db.save_goals(server_id)
        
        command = bot.get_command('list')
        await command.callback(mock_ctx)
        
        # Verify embed contains all objectives
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert len(called_embed.fields) == 3
        
        # Verify status is included in formatted text
        for field in called_embed.fields:
            objective_number = field.name.split()[-1]
            status = server_goals["objectives"][objective_number]["status"]
            field_value = str(field.value).lower()
            assert status.lower() in field_value, f"Status '{status}' not found in field value: {field_value}"

    @pytest.mark.asyncio
    async def test_multiple_servers(self, bot, mock_ctx, mock_ctx_second_server, mock_anthropic_response):
        """Test objectives staying separate between servers"""
        server1_id = str(mock_ctx.guild.id)
        server2_id = str(mock_ctx_second_server.guild.id)
        
        def mock_create(*args, **kwargs):
            return mock_anthropic_response

        with patch.object(bot.anthropic.messages, 'create', side_effect=mock_create):
            command = bot.get_command('set_objective')
            
            # Create objective in first server
            await command.callback(mock_ctx, objective_text="Server 1 objective")
            
            # Create objective in second server
            await command.callback(mock_ctx_second_server, objective_text="Server 2 objective")
            
            # Verify separate data
            server1_goals = bot.db.get_goals(server1_id)
            server2_goals = bot.db.get_goals(server2_id)
            
            assert len(server1_goals["objectives"]) == 1
            assert len(server2_goals["objectives"]) == 1
            assert server1_goals != server2_goals
            
            # Verify separate files exist
            assert os.path.exists(bot.db.get_server_filename(server1_id))
            assert os.path.exists(bot.db.get_server_filename(server2_id))

@pytest.mark.asyncio
class TestObjectiveCRUD:
    async def test_add_progress(self, bot, mock_ctx):
        """Test adding progress updates"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Setup initial objective
        server_goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        bot.db.save_goals(server_id)
        
        # Add progress
        command = bot.get_command('add_progress')
        update_text = "Made progress on objective"
        await command.callback(mock_ctx, objective_id="1", update_text=update_text)
        
        # Verify updates
        updated_goals = bot.db.get_goals(server_id)
        assert len(updated_goals["updates"]) == 1
        assert updated_goals["updates"][0]["objective_id"] == "1"
        assert updated_goals["updates"][0]["text"] == update_text
        
        # Verify embed
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert called_embed.title == "📝 Progress Update Added"
        assert called_embed.description == "Update added to Objective 1"
        assert called_embed.color == Color.green()

    async def test_view_progress(self, bot, mock_ctx):
        """Test viewing progress updates"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Setup initial objective and updates
        server_goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        
        updates = [f"Update {i}" for i in range(6)]
        for update in updates:
            server_goals["updates"].append({
                "objective_id": "1",
                "text": update,
                "updated_by": "123456789",
                "updated_at": str(datetime.datetime.now())
            })
        bot.db.save_goals(server_id)
        
        # View progress
        command = bot.get_command('view_progress')
        await command.callback(mock_ctx, objective_id="1")
        
        # Verify response
        called_embed = mock_ctx.send.call_args[1]['embed']
        assert len(called_embed.fields) == 5
        for i, update in enumerate(updates[-5:]):
            assert update in called_embed.fields[i].value

    async def test_clear_all(self, bot, mock_ctx):
        """Test clearing all objectives"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Setup test data
        server_goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        bot.db.save_goals(server_id)
        
        # Setup mocks
        mock_ctx.author.guild_permissions.administrator = True
        confirm_msg = AsyncMock()
        mock_ctx.send.return_value = confirm_msg
        mock_reaction = AsyncMock()
        mock_reaction.emoji = "✅"
        bot.wait_for = AsyncMock(return_value=(mock_reaction, mock_ctx.author))
        
        # Execute clear
        command = bot.get_command('clear_all')
        await command.callback(mock_ctx)
        
        # Verify cleared data
        cleared_goals = bot.db.get_goals(server_id)
        assert len(cleared_goals["objectives"]) == 0
        assert len(cleared_goals["updates"]) == 0
        
        # Verify messages
        assert any(call.args[0] == "⚠️ **WARNING**: This will delete ALL objectives and updates. React with ✅ to confirm." 
                  for call in mock_ctx.send.call_args_list)
        
        final_embed = mock_ctx.send.call_args_list[-1][1]['embed']
        assert final_embed.title == "💥 Database Cleared"
        assert final_embed.color == Color.red()

    async def test_clear_all_timeout(self, bot, mock_ctx):
        """Test clear_all when confirmation times out"""
        server_id = str(mock_ctx.guild.id)
        server_goals = bot.db.get_goals(server_id)
        
        # Setup initial data
        server_goals["objectives"]["1"] = {
            "text": "Test objective",
            "created_by": "123456789",
            "created_at": str(datetime.datetime.now()),
            "status": "active"
        }
        bot.db.save_goals(server_id)
        
        # Setup mocks
        mock_ctx.author.guild_permissions.administrator = True
        confirm_msg = AsyncMock()
        mock_ctx.send.return_value = confirm_msg
        bot.wait_for = AsyncMock(side_effect=TimeoutError())
        
        # Execute command
        command = bot.get_command('clear_all')
        await command.callback(mock_ctx)
        
        # Verify timeout handled correctly
        mock_ctx.send.assert_called_with("Clear all operation cancelled (timed out)")
        after_goals = bot.db.get_goals(server_id)
        assert len(after_goals["objectives"]) == 1

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