import discord
from discord.ext import commands
from anthropic import Anthropic
import json
import datetime
import os
from discord import Embed
from dotenv import load_dotenv
from .setup_commands import setup_commands
import logging
from discord import Color, Embed


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
    def __init__(self, filename="goals.json"):
        self.filename = filename
        logger.info(f"Initializing database with file: {self.filename}")
        try:
            logger.info(f"Directory contents: {os.listdir('.')}")
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
        self.goals = self.load_goals()

    def load_goals(self) -> dict:
        logger.info("Loading goals from file")
        default_data = {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump(default_data, f, indent=2)
            return default_data
            
        try:
            with open(self.filename, 'r') as f:
                content = f.read().strip()
                if not content:
                    with open(self.filename, 'w') as f:
                        json.dump(default_data, f, indent=2)
                    return default_data
                return json.loads(content)
        except json.JSONDecodeError:
            if os.path.exists(self.filename):
                backup_name = f"{self.filename}.backup-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
                os.rename(self.filename, backup_name)
            
            with open(self.filename, 'w') as f:
                json.dump(default_data, f, indent=2)
            return default_data
    
    def save_goals(self):
        if os.path.exists(self.filename):
            backup_name = f"{self.filename}.backup"
            try:
                with open(self.filename, 'r') as original:
                    with open(backup_name, 'w') as backup:
                        backup.write(original.read())
            except Exception as e:
                print(f"Failed to create backup: {e}")
        
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.goals, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save goals: {e}")
            if os.path.exists(backup_name):
                os.replace(backup_name, self.filename)

class CompanyAssistant(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        # Fix: Pass command_prefix first
        super().__init__(
            command_prefix='!',  # This needs to come first
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
        # Remove TextBlock wrapper
        text = text.replace("TextBlock(text='", "").replace("')", "")
        text = text.replace("[TextBlock(text=", "").replace(")]", "")
        # Remove escape characters
        text = text.replace("\\n", "\n")
        # Remove list wrapper if present
        text = text.strip("[]'")
        return text
    
    def format_section(self, text: str, max_length: int = 1024) -> str:
        """Format a section of text with proper line breaks and bullet points"""
        text = self.clean_text(text)
        
        # Split into sections
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
        
        # Format each section
        formatted_text = ""
        for section in sections:
            if ":" in section:
                title, content = section.split(":", 1)
                content = content.strip()
                
                # Format bullet points - convert all dashes to bullets
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
        
        # Truncate if necessary
        if len(formatted_text) > max_length:
            return formatted_text[:max_length-3] + "..."
        return formatted_text

    async def _set_objective_impl(self, ctx, objective_text):
        """Implementation of set_objective command"""
        try:
            logger.info(f"Setting objective: {objective_text[:50]}...")  # Log first 50 chars
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
            logger.info("Got response from Anthropic")
            
            structured_objective = str(message.content)
            objective_id = str(len(self.db.goals["objectives"]) + 1)
            
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
            
            self.db.goals["objectives"][objective_id] = {
                "text": structured_objective,
                "original_text": objective_text,
                "created_by": str(ctx.author.id),
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
            
            self.db.save_goals()
            await ctx.send(embed=embed)
            
        except Exception as e:
                logger.error(f"Error in set_objective: {e}", exc_info=True)
                error_embed = Embed(
                    title="❌ Error Setting Objective",
                    description=f"An error occurred: {str(e)}",
                    color=Color.red()
                )
                await ctx.send(embed=error_embed)
                return  # Return here to prevent the exception from propagating

    async def _clear_all_impl(self, ctx):
        """Nuclear option to clear all objectives (admin only, testing)"""
        # Check if user is admin
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Only administrators can use this command!")
            return

        # Reset database to default state
        self.db.goals = {
            "objectives": {},
            "updates": [],
            "metrics": {}
        }
        self.db.save_goals()
        
        embed = Embed(
            title="💥 Database Cleared",
            description="All objectives and updates have been removed.",
            color=Color.red()
        )
        embed.set_footer(text=f"Cleared by admin: {ctx.author.name}")
        await ctx.send(embed=embed)

    async def _list_objectives_impl(self, ctx):
        """Implementation of list command"""
        try:
            if not self.db.goals["objectives"]:
                await ctx.send("No objectives set yet! Use `!set_objective` to create one.")
                return
            
            # Create initial embed
            embed = Embed(
                title="📊 Company Objectives",
                color=Color.blue(),
                description="Current company objectives and their status."
            )
            
            # Sort objectives by ID
            sorted_objectives = dict(sorted(
                self.db.goals["objectives"].items(),
                key=lambda x: int(x[0])
            ))
            
            current_embed = embed
            page = 1
            objectives_in_current_embed = 0
            
            for obj_id, obj in sorted_objectives.items():
                formatted_value = self.format_section(obj["text"])
                
                # Check if adding this field would exceed Discord's limits
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
            
            # Send the last embed if it has any fields
            if len(current_embed.fields) > 0:
                await ctx.send(embed=current_embed)
            
        except Exception as e:
            error_embed = Embed(
                title="❌ Error Listing Objectives",
                description=f"An error occurred: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)
            print(f"Detailed error: {e}")

    async def _update_objective_status_impl(self, ctx, objective_id: str, status: str):
        """Update objective status (active/completed/cancelled)"""
        if objective_id not in self.db.goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        valid_statuses = ["active", "completed", "cancelled"]
        if status.lower() not in valid_statuses:
            await ctx.send(f"Invalid status. Please use one of: {', '.join(valid_statuses)}")
            return
            
        self.db.goals["objectives"][objective_id]["status"] = status.lower()
        self.db.save_goals()
        
        embed = Embed(
            title="✏️ Objective Updated",
            description=f"Objective {objective_id} status changed to: {status}",
            color=Color.green()
        )
        await ctx.send(embed=embed)

    async def _delete_objective_impl(self, ctx, objective_id: str):
        """Delete an objective"""
        if objective_id not in self.db.goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        # Optional: Only allow deletion by creator or admin
        if str(ctx.author.id) != self.db.goals["objectives"][objective_id]["created_by"]:
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("You can only delete objectives you created!")
                return
                
        del self.db.goals["objectives"][objective_id]
        self.db.save_goals()
        
        embed = Embed(
            title="🗑️ Objective Deleted",
            description=f"Objective {objective_id} has been deleted",
            color=Color.red()
        )
        await ctx.send(embed=embed)

    async def _add_progress_impl(self, ctx, objective_id: str, update_text: str):
        """Add a progress update to an objective"""
        if objective_id not in self.db.goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        update = {
            "objective_id": objective_id,
            "text": update_text,
            "updated_by": str(ctx.author.id),
            "updated_at": str(datetime.datetime.now())
        }
        
        self.db.goals["updates"].append(update)
        self.db.save_goals()
        
        embed = Embed(
            title="📝 Progress Update Added",
            description=f"Update added to Objective {objective_id}",
            color=Color.green()
        )
        embed.add_field(name="Update", value=update_text, inline=False)
        await ctx.send(embed=embed)
    
    async def _view_progress_impl(self, ctx, objective_id: str):
        """View progress updates for an objective"""
        if objective_id not in self.db.goals["objectives"]:
            await ctx.send(f"Objective {objective_id} not found!")
            return
            
        updates = [u for u in self.db.goals["updates"] 
                  if u["objective_id"] == objective_id]
        
        if not updates:
            await ctx.send(f"No progress updates found for Objective {objective_id}")
            return
        
        embed = Embed(
            title=f"📊 Progress History - Objective {objective_id}",
            color=Color.blue(),
            description=f"Recent updates for objective {objective_id}"
        )
        
        # Show last 5 updates
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
    
  # In goals_bot.py, add to CompanyAssistant class:
    async def _reset_railway_impl(self, ctx):
        """Reset the database file (admin only)"""
        if not await self._check_admin_permission(ctx):
            return
            
        try:
            if os.path.exists(self.db.filename):
                os.remove(self.db.filename)
                self.db = GoalsDatabase()  # Reinitialize with fresh database
                
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