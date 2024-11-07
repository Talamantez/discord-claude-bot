import discord
from discord.ext import commands
from anthropic import Anthropic
import json
import datetime
import os
from discord import Embed
from dotenv import load_dotenv
import logging
from discord import Color, Embed
try:
    from .setup_commands import setup_commands
except ImportError:
    from src.setup_commands import setup_commands

# Load environment variables
load_dotenv()

# Set up logging at the top of goals_bot.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GoalsDatabase:
    def __init__(self, base_filename="goals"):
        """
        Initialize database with server-specific files
        base_filename: Base name for database files (without .json extension)
        """
        self.base_filename = base_filename
        self.server_data = {}
        logger.info(f"Initializing database with base filename: {self.base_filename}")

    def get_server_filename(self, server_id):
        """Get the filename for a specific server"""
        return f"{self.base_filename}_{server_id}.json"

    def load_goals(self, server_id) -> dict:
        """Load goals for a specific server"""
        logger.info(f"Loading goals for server {server_id}")
        filename = self.get_server_filename(server_id)
        
        default_data = {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                json.dump(default_data, f, indent=2)
            return default_data
            
        try:
            with open(filename, 'r') as f:
                content = f.read().strip()
                if not content:
                    with open(filename, 'w') as f:
                        json.dump(default_data, f, indent=2)
                    return default_data
                return json.loads(content)
        except json.JSONDecodeError:
            if os.path.exists(filename):
                backup_name = f"{filename}.backup-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                os.rename(filename, backup_name)
            
            with open(filename, 'w') as f:
                json.dump(default_data, f, indent=2)
            return default_data

    def get_goals(self, server_id):
        """Get goals for a specific server, loading if necessary"""
        if server_id not in self.server_data:
            self.server_data[server_id] = self.load_goals(server_id)
        return self.server_data[server_id]

    def save_goals(self, server_id):
        """Save goals for a specific server"""
        if server_id not in self.server_data:
            return
            
        filename = self.get_server_filename(server_id)
        backup_name = f"{filename}.backup"
        
        # Create backup
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as original:
                    with open(backup_name, 'w') as backup:
                        backup.write(original.read())
            except Exception as e:
                logger.error(f"Failed to create backup: {e}")
        
        # Save new data
        try:
            with open(filename, 'w') as f:
                json.dump(self.server_data[server_id], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save goals: {e}")
            if os.path.exists(backup_name):
                os.replace(backup_name, filename)
class CompanyAssistant(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents
        )
        
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.db = GoalsDatabase()

    async def setup_hook(self):
        """Set up bot commands"""
        logger.info("Setting up bot commands")
        setup_commands(self)
        logger.info("Bot commands setup complete")

    async def on_ready(self):
        logger.info(f'Bot is ready and logged in as {self.user}')
        logger.info(f'Connected to {len(self.guilds)} guilds')

    async def on_error(self, event, *args, **kwargs):
        print(f"Error in {event}: {args} {kwargs}")
        import traceback
        traceback.print_exc()
    
    def clean_text(self, text: str) -> str:
        """Clean up text by removing TextBlock wrapper and other artifacts"""
        text = str(text)
        text = text.replace("TextBlock(text='", "").replace("')", "")
        text = text.replace("[TextBlock(text=", "").replace(")]", "")
        text = text.replace("\\n", "\n")
        text = text.strip("[]'")
        return text
    
    def format_section(self, text: str, max_length: int = 1024) -> str:
        """Format a section of text with proper line breaks and bullet points"""
        text = self.clean_text(text)
        
        sections = []
        current_section = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if any(line.startswith(s) for s in ["1. ", "2. ", "3. "]):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
            current_section.append(line)
            
        if current_section:
            sections.append('\n'.join(current_section))
        
        formatted_text = ""
        for section in sections:
            if ":" in section:
                title, content = section.split(":", 1)
                content = content.strip()
                
                lines = content.split('\n')
                formatted_lines = []
                for line in lines:
                    if line.strip().startswith('- '):
                        formatted_lines.append('• ' + line.strip()[2:])
                    else:
                        formatted_lines.append(line)
                content = '\n'.join(formatted_lines)
                
                formatted_text += f"**{title.strip()}**\n{content}\n\n"
            else:
                formatted_text += f"{section}\n\n"
        
        if len(formatted_text) > max_length:
            return formatted_text[:max_length-3] + "..."
        return formatted_text

    async def _set_objective_impl(self, ctx, objective_text):
        """Implementation of set_objective command"""
        try:
            server_id = str(ctx.guild.id)
            logger.info(f"Setting objective for server {server_id}: {objective_text[:50]}...")
            
            message = self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"""Please structure this business objective into a SMART goal format:

                    Objective: {objective_text}
                    
                    Format your response as:
                    1. Structured Objective:
                    [Describe the goal using SMART criteria]

                    2. Key Metrics:
                    • [Key metric 1]
                    • [Key metric 2]
                    • [etc...]

                    3. Suggested Timeline:
                    • [Timeline point 1]
                    • [Timeline point 2]
                    • [etc...]"""
                }]
            )
            
            structured_objective = str(message.content)
            server_goals = self.db.get_goals(server_id)
            objective_id = str(len(server_goals["objectives"]) + 1)
            
            formatted_objective = self.format_section(structured_objective)
            
            embed = Embed(
                title="📋 New Objective Created",
                color=Color.green()
            )
            
            embed.add_field(
                name="SMART Goal",
                value=formatted_objective,
                inline=False
            )
            
            embed.set_footer(text=f"Objective ID: {objective_id} | Created by {ctx.author.name}")
            
            server_goals["objectives"][objective_id] = {
                "text": structured_objective,
                "original_text": objective_text,
                "created_by": str(ctx.author.id),
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
            
            self.db.save_goals(server_id)
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in set_objective: {e}", exc_info=True)
            error_embed = Embed(
                title="❌ Error Setting Objective",
                description=f"An error occurred: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)



    async def _clear_all_impl(self, ctx):
        """Nuclear option to clear all objectives (admin only, testing)"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command!")
            return

        server_id = str(ctx.guild.id)
        self.db.server_data[server_id] = {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        self.db.save_goals(server_id)
        
        embed = Embed(
            title="💥 Database Cleared",
            description="All objectives and updates have been removed.",
            color=Color.red()
        )
        embed.set_footer(text=f"Cleared by admin: {ctx.author.name}")
        await ctx.send(embed=embed)

    async def _add_progress_impl(self, ctx, objective_id: str, update_text: str):
        """Add a progress update to an objective"""
        server_id = str(ctx.guild.id)
        server_goals = self.db.get_goals(server_id)
        
        if objective_id not in server_goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        update = {
            "objective_id": objective_id,
            "text": update_text,
            "updated_by": str(ctx.author.id),
            "updated_at": str(datetime.datetime.now())
        }
        
        server_goals["updates"].append(update)
        self.db.save_goals(server_id)
        
        embed = Embed(
            title="📝 Progress Update Added",
            description=f"Update added to Objective {objective_id}",
            color=Color.green()
        )
        embed.add_field(name="Update", value=update_text, inline=False)
        await ctx.send(embed=embed)

    async def _view_progress_impl(self, ctx, objective_id: str):
        """View progress updates for an objective"""
        server_id = str(ctx.guild.id)
        server_goals = self.db.get_goals(server_id)
        
        if objective_id not in server_goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        updates = [u for u in server_goals["updates"] 
                  if u["objective_id"] == objective_id]
        
        if not updates:
            await ctx.send(f"No progress updates found for Objective {objective_id}")
            return
        
        embed = Embed(
            title=f"📊 Progress History - Objective {objective_id}",
            color=Color.blue(),
            description=f"Recent updates for objective {objective_id}"
        )
        
        for update in updates[-5:]:
            updated_at = datetime.datetime.fromisoformat(str(update['updated_at']))
            formatted_date = updated_at.strftime("%Y-%m-%d %H:%M")
            embed.add_field(
                name=f"Update from {formatted_date}",
                value=update['text'],
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def _check_admin_permission(self, ctx):
        """Check if user has admin permissions"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command!")
            return False
        return True

    async def _clear_all_impl(self, ctx):
        """Nuclear option to clear all objectives (admin only, testing)"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command!")
            return

        server_id = str(ctx.guild.id)
        # Reset server-specific database to default state
        self.db.server_data[server_id] = {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        self.db.save_goals(server_id)
        
        embed = Embed(
            title="💥 Database Cleared",
            description="All objectives and updates have been removed.",
            color=Color.red()
        )
        embed.set_footer(text=f"Cleared by admin: {ctx.author.name}")
        await ctx.send(embed=embed)

    async def _update_objective_status_impl(self, ctx, objective_id: str, status: str):
        """Update objective status (active/completed/cancelled)"""
        server_id = str(ctx.guild.id)
        server_goals = self.db.get_goals(server_id)
        
        if objective_id not in server_goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        valid_statuses = ["active", "completed", "cancelled"]
        if status.lower() not in valid_statuses:
            await ctx.send(f"Invalid status. Please use one of: {', '.join(valid_statuses)}")
            return
            
        server_goals["objectives"][objective_id]["status"] = status.lower()
        self.db.save_goals(server_id)
        
        embed = Embed(
            title="✏️ Objective Updated",
            description=f"Objective {objective_id} status changed to: {status}",
            color=Color.green()
        )
        await ctx.send(embed=embed)

    async def _list_objectives_impl(self, ctx):
        """Implementation of list command"""
        try:
            server_id = str(ctx.guild.id)
            server_goals = self.db.get_goals(server_id)
            
            if not server_goals["objectives"]:
                await ctx.send("No objectives set yet! Use `!set_objective` to create one.")
                return
            
            embed = Embed(
                title="📊 Company Objectives",
                color=Color.blue(),
                description="Current company objectives and their status."
            )
            
            sorted_objectives = dict(sorted(
                server_goals["objectives"].items(),
                key=lambda x: int(x[0])
            ))
            
            current_embed = embed
            page = 1
            objectives_in_current_embed = 0
            
            status_emojis = {
                "active": "🟢",
                "completed": "✅",
                "cancelled": "⛔"
            }
            
            for obj_id, obj in sorted_objectives.items():
                # Include status in formatted value
                status = obj.get("status", "active")
                status_emoji = status_emojis.get(status, "❔")
                formatted_text = self.format_section(obj["text"])
                
                # Add status line at the top
                formatted_value = f"{status_emoji} Status: {status.upper()}\n\n{formatted_text}"
                
                if len(current_embed) + len(formatted_value) > 5500 or objectives_in_current_embed >= 3:
                    await ctx.send(embed=current_embed)
                    page += 1
                    current_embed = Embed(
                        title=f"📊 Company Objectives (Page {page})",
                        color=Color.blue()
                    )
                    objectives_in_current_embed = 0
                
                current_embed.add_field(
                    name=f"Objective {obj_id}",
                    value=formatted_value,
                    inline=False
                )
                objectives_in_current_embed += 1
            
            if len(current_embed.fields) > 0:
                await ctx.send(embed=current_embed)
                
        except Exception as e:
            error_embed = Embed(
                title="❌ Error Listing Objectives",
                description=f"An error occurred: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)

    async def _reset_railway_impl(self, ctx):
        """Reset the database file (admin only)"""
        if not await self._check_admin_permission(ctx):
            return
            
        try:
            server_id = str(ctx.guild.id)
            filename = self.db.get_server_filename(server_id)
            
            if os.path.exists(filename):
                os.remove(filename)
                # Reset server data
                self.db.server_data[server_id] = self.db.load_goals(server_id)
                
                embed = Embed(
                    title="🔄 Database Reset",
                    description="Database has been reset to initial state.",
                    color=Color.green()
                )
                embed.set_footer(text=f"Reset by admin: {ctx.author.name}")
                await ctx.send(embed=embed)
            else:
                await ctx.send("No database file found!")
        except Exception as e:
            error_embed = Embed(
                title="❌ Reset Failed",
                description=f"Error: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)

def main():
    logger.info("Starting bot initialization")
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        logger.error("DISCORD_TOKEN not found in environment variables")
        raise ValueError("DISCORD_TOKEN not found in environment variables")
        
    bot = CompanyAssistant()
    try:
        logger.info("Starting bot")
        bot.run(discord_token)
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()