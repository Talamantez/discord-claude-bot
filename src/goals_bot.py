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
from discord.ui import Button, View
from discord import ButtonStyle, Interaction

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
        text = text.replace(', type="text"', '')  # Remove stray type attribute
        return text.strip("[]'")
    
    def format_section(self, text: str, max_field_length: int = 1024) -> list:
        """
        Format a section of text with proper line breaks and bullet points.
        Returns a list of formatted chunks that fit within Discord's limits.
        """
        text = self.clean_text(text)
        
        # Split into main sections (Structured Objective, Key Metrics, etc.)
        sections = []
        current_section = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Check for new main section
            if any(line.startswith(s) for s in ["1. ", "2. ", "3. "]):
                if current_section:
                    sections.append('\n'.join(current_section))
                    current_section = []
            current_section.append(line)
                
        if current_section:
            sections.append('\n'.join(current_section))

        # Format each section with proper formatting
        formatted_chunks = []
        current_chunk = ""
        
        for section in sections:
            formatted_section = ""
            if ":" in section:
                title, content = section.split(":", 1)
                content = content.strip()
                
                # Format bullet points
                lines = content.split('\n')
                formatted_lines = []
                for line in lines:
                    if line.strip().startswith('- ') or line.strip().startswith('• '):
                        formatted_lines.append('• ' + line.strip()[2:])
                    elif line.strip().startswith('* '):
                        formatted_lines.append('• ' + line.strip()[2:])
                    else:
                        formatted_lines.append(line)
                content = '\n'.join(formatted_lines)
                
                formatted_section = f"**{title.strip()}**\n{content}\n\n"
            else:
                formatted_section = f"{section}\n\n"
                
            # Check if adding this section would exceed field length
            if len(current_chunk + formatted_section) > max_field_length:
                if current_chunk:
                    formatted_chunks.append(current_chunk.strip())
                current_chunk = formatted_section
            else:
                current_chunk += formatted_section
                
        if current_chunk:
            formatted_chunks.append(current_chunk.strip())
            
        return formatted_chunks

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
        """Implementation of list command with enhanced visual hierarchy"""
        try:
            server_id = str(ctx.guild.id)
            server_goals = self.db.get_goals(server_id)
            
            if not server_goals["objectives"]:
                # Keep original plain message for empty state to match tests
                await ctx.send("No objectives set yet! Use `!set_objective` to create one.")
                return
            
            # Progress overview
            total = len(server_goals["objectives"])
            active = sum(1 for obj in server_goals["objectives"].values() if obj.get("status") == "active")
            completed = sum(1 for obj in server_goals["objectives"].values() if obj.get("status") == "completed")
            
            embed = Embed(
                title="📊 Company Objectives",  # Keep original title for test compatibility
                color=Color.blue(),
                description=f"**Progress Overview**\n"
                        f"🎯 Total Objectives: {total}\n"
                        f"🔄 Active: {active}\n"
                        f"✅ Completed: {completed}\n"
            )
            
            sorted_objectives = dict(sorted(
                server_goals["objectives"].items(),
                key=lambda x: int(x[0])
            ))
            
            current_embed = embed
            page = 1
            objectives_in_current_embed = 0
            
            status_styles = {
                "active": ("🟢", "Active", Color.green()),
                "completed": ("✅", "Completed", Color.blue()),
                "cancelled": ("⛔", "Cancelled", Color.red())
            }
            
            for obj_id, obj in sorted_objectives.items():
                status = obj.get("status", "active")
                emoji, status_text, status_color = status_styles.get(status, ("❔", "Unknown", Color.greyple()))
                
                # Format the content with visual hierarchy
                formatted_chunks = self.format_section(obj["text"])
                content = formatted_chunks[0] if formatted_chunks else ""
                
                # Create visually distinct field for each objective
                # Remove '#' from objective ID in field name for test compatibility
                field_value = (
                    f"{emoji} **Status**: `{status_text}`\n"
                    f"📅 Created: {obj['created_at'][:10]}\n"
                    f"👤 Owner: <@{obj['created_by']}>\n\n"
                    f"{content}\n\n"
                    f"*Use `!view_progress {obj_id}` for detailed updates*"
                )
                
                if len(current_embed) + len(field_value) > 5500 or objectives_in_current_embed >= 3:
                    await ctx.send(embed=current_embed)
                    page += 1
                    current_embed = Embed(
                        title=f"📊 Company Objectives (Page {page})",  # Keep consistent title format
                        color=Color.blue()
                    )
                    objectives_in_current_embed = 0
                
                current_embed.add_field(
                    name=f"🎯 Objective {obj_id}",  # Remove '#' for test compatibility
                    value=field_value,
                    inline=False
                )
                objectives_in_current_embed += 1
            
            if len(current_embed.fields) > 0:
                # Create view for list management buttons
                view = ObjectiveListView()
                current_embed.set_footer(text="💡 Tip: Use !help objectives for more commands")
                await ctx.send(embed=current_embed, view=view)
                
        except Exception as e:
            error_embed = Embed(
                title="❌ Error Listing Objectives",
                description=f"An error occurred: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)
    async def _set_objective_impl(self, ctx, objective_text):
        """Implementation of set_objective command with interactive buttons"""
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
            
            structured_objective = self.clean_text(str(message.content))
            server_goals = self.db.get_goals(server_id)
            objective_id = str(len(server_goals["objectives"]) + 1)
            
            # Create initial embed
            embed = Embed(
                title="📋 New Strategic Objective",
                color=Color.green()
            )

            # Add overview section
            embed.add_field(
                name="🎯 Overview",
                value=f"Objective ID: `#{objective_id}`\nStatus: `Active`\nOwner: {ctx.author.mention}\n",
                inline=False
            )

            # Process and format the structured content
            sections = structured_objective.split('\n\n')
            for section in sections:
                if "1. Structured Objective:" in section:
                    content = section.replace("1. Structured Objective:", "").strip()
                    embed.add_field(
                        name="📝 Key Objective",
                        value=f"```{content}```",
                        inline=False
                    )
                
                elif "2. Key Metrics:" in section:
                    content = section.replace("2. Key Metrics:", "").strip()
                    metrics = content.split('\n')
                    formatted_metrics = []
                    for metric in metrics:
                        if metric.strip():
                            formatted_metrics.append(f"📊 {metric.strip().replace('•', '').strip()}")
                    embed.add_field(
                        name="📈 Success Metrics",
                        value="\n".join(formatted_metrics),
                        inline=False
                    )
                
                elif "3. Suggested Timeline:" in section:
                    content = section.replace("3. Suggested Timeline:", "").strip()
                    timeline = content.split('\n')
                    formatted_timeline = []
                    for i, milestone in enumerate(timeline):
                        if milestone.strip():
                            stage_emoji = ["🔵", "🟡", "🟢", "💫", "✨"][i % 5]
                            formatted_timeline.append(
                                f"{stage_emoji} {milestone.strip().replace('•', '').strip()}"
                            )
                    embed.add_field(
                        name="⏱️ Implementation Timeline",
                        value="\n".join(formatted_timeline),
                        inline=False
                    )

            # Add quick reference footer
            embed.set_footer(
                text=f"Use the buttons below to manage this objective"
            )

            # Save to database before creating view
            server_goals["objectives"][objective_id] = {
                "text": structured_objective,
                "original_text": objective_text,
                "created_by": str(ctx.author.id),
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
            self.db.save_goals(server_id)

            # Create view with buttons after saving
            view = ObjectiveView(objective_id)
            
            # Send message with view
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error in set_objective: {e}", exc_info=True)
            error_embed = Embed(
                title="❌ Error Setting Objective",
                description=f"An error occurred: {str(e)}",
                color=Color.red()
            )
            await ctx.send(embed=error_embed)
        async def _list_objectives_impl(self, ctx):
            """Implementation of list command with enhanced visual hierarchy"""
            try:
                view = ObjectiveListView()
                server_id = str(ctx.guild.id)
                server_goals = self.db.get_goals(server_id)
                
                if not server_goals["objectives"]:
                    # Friendly empty state
                    embed = Embed(
                        title="📋 Company Objectives",
                        description="No objectives set yet! Use `!set_objective` to create your first strategic goal.",
                        color=Color.blue()
                    )
                    embed.add_field(
                        name="Getting Started",
                        value="Example: `!set_objective increase monthly active users by 25% in Q2`",
                        inline=False
                    )
                    await ctx.send(embed=embed, view=view)
                    return
                
                # Progress overview
                total = len(server_goals["objectives"])
                active = sum(1 for obj in server_goals["objectives"].values() if obj.get("status") == "active")
                completed = sum(1 for obj in server_goals["objectives"].values() if obj.get("status") == "completed")
                
                embed = Embed(
                    title="📊 Strategic Objectives Dashboard",
                    color=Color.blue(),
                    description=f"**Progress Overview**\n"
                            f"🎯 Total Objectives: {total}\n"
                            f"🔄 Active: {active}\n"
                            f"✅ Completed: {completed}\n"
                )
                
                sorted_objectives = dict(sorted(
                    server_goals["objectives"].items(),
                    key=lambda x: int(x[0])
                ))
                
                current_embed = embed
                page = 1
                objectives_in_current_embed = 0
                
                status_styles = {
                    "active": ("🟢", "Active", Color.green()),
                    "completed": ("✅", "Completed", Color.blue()),
                    "cancelled": ("⛔", "Cancelled", Color.red())
                }
                
                for obj_id, obj in sorted_objectives.items():
                    status = obj.get("status", "active")
                    emoji, status_text, status_color = status_styles.get(status, ("❔", "Unknown", Color.greyple()))
                    
                    # Format the content with visual hierarchy
                    formatted_chunks = self.format_section(obj["text"])
                    content = formatted_chunks[0] if formatted_chunks else ""
                    
                    # Create visually distinct field for each objective
                    field_value = (
                        f"{emoji} **Status**: `{status_text}`\n"
                        f"📅 Created: {obj['created_at'][:10]}\n"
                        f"👤 Owner: <@{obj['created_by']}>\n\n"
                        f"{content}\n\n"
                        f"*Use `!view_progress {obj_id}` for detailed updates*"
                    )
                    
                    if len(current_embed) + len(field_value) > 5500 or objectives_in_current_embed >= 3:
                        await ctx.send(embed=current_embed)
                        page += 1
                        current_embed = Embed(
                            title=f"📊 Strategic Objectives (Page {page})",
                            color=Color.blue()
                        )
                        objectives_in_current_embed = 0
                    
                    current_embed.add_field(
                        name=f"🎯 Objective #{obj_id}",
                        value=field_value,
                        inline=False
                    )
                    objectives_in_current_embed += 1
                
                if len(current_embed.fields) > 0:
                    current_embed.set_footer(text="💡 Tip: Use !help objectives for more commands")
                    await ctx.send(embed=current_embed)
                    
            except Exception as e:
                error_embed = Embed(
                    title="❌ Error Listing Objectives",
                    description=f"An error occurred: {str(e)}",
                    color=Color.red()
                )
                await ctx.send(embed=error_embed)

class ObjectiveView(View):
    def __init__(self, objective_id: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.objective_id = str(objective_id)
        
        # Quick Status Buttons Row
        complete_btn = Button(
            style=ButtonStyle.success,
            label="Mark Complete ✅",
            custom_id=f"complete_{self.objective_id}",
            row=0
        )
        complete_btn.callback = self.complete_callback
        self.add_item(complete_btn)
        
        cancel_btn = Button(
            style=ButtonStyle.danger,
            label="Cancel ⛔",
            custom_id=f"cancel_{self.objective_id}",
            row=0
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)
        
        reactivate_btn = Button(
            style=ButtonStyle.secondary,
            label="Reactivate 🔄",
            custom_id=f"reactivate_{self.objective_id}",
            row=0
        )
        reactivate_btn.callback = self.reactivate_callback
        self.add_item(reactivate_btn)
        
        # Progress Buttons Row
        update_btn = Button(
            style=ButtonStyle.primary,
            label="Add Update 📝",
            custom_id=f"update_{self.objective_id}",
            row=1
        )
        update_btn.callback = self.update_callback
        self.add_item(update_btn)
        
        history_btn = Button(
            style=ButtonStyle.secondary,
            label="View History 📊",
            custom_id=f"history_{self.objective_id}",
            row=1
        )
        history_btn.callback = self.history_callback
        self.add_item(history_btn)
        
        # Management Buttons Row
        edit_btn = Button(
            style=ButtonStyle.secondary,
            label="Edit Details ✏️",
            custom_id=f"edit_{self.objective_id}",
            row=2
        )
        edit_btn.callback = self.edit_callback
        self.add_item(edit_btn)
        
        reminder_btn = Button(
            style=ButtonStyle.secondary,
            label="Set Reminder ⏰",
            custom_id=f"remind_{self.objective_id}",
            row=2
        )
        reminder_btn.callback = self.reminder_callback
        self.add_item(reminder_btn)

    async def complete_callback(self, interaction: Interaction):
        try:
            # Create follow-up buttons
            follow_up_view = View(timeout=60)
            
            update_btn = Button(label="Add Final Update", style=ButtonStyle.primary)
            update_btn.callback = self.update_callback
            follow_up_view.add_item(update_btn)
            
            followup_btn = Button(label="Create Follow-up", style=ButtonStyle.success)
            followup_btn.callback = lambda i: i.response.send_modal(self.create_objective_modal())
            follow_up_view.add_item(followup_btn)
            
            archive_btn = Button(label="Archive", style=ButtonStyle.secondary)
            archive_btn.callback = self.archive_callback
            follow_up_view.add_item(archive_btn)
            
            await interaction.response.send_message(
                "🎉 Objective completed! What would you like to do next?",
                ephemeral=True,
                view=follow_up_view
            )
        except Exception as e:
            await interaction.response.send_message(
                "❌ Error updating status. Please try again.",
                ephemeral=True
            )

    async def cancel_callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            self.create_text_modal(
                "Cancel Objective",
                "Please provide a reason for cancellation",
                required=True
            )
        )

    async def reactivate_callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            self.create_text_modal(
                "Reactivate Objective",
                "Please provide context for reactivation",
                required=True
            )
        )

    async def update_callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            self.create_text_modal(
                "Add Progress Update",
                "What progress has been made?",
                placeholder="Describe your progress..."
            )
        )

    async def history_callback(self, interaction: Interaction):
        # Command will be implemented in the bot's command handler
        await interaction.response.send_message(
            f"Loading history... Use: `!view_progress {self.objective_id}`",
            ephemeral=True
        )

    async def edit_callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            self.create_text_modal(
                "Edit Objective",
                "Update objective details",
                placeholder="Modify the objective...",
                max_length=2000
            )
        )

    async def reminder_callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            self.create_text_modal(
                "Set Reminder",
                "When to remind?",
                placeholder="e.g. tomorrow at 2pm, in 3 days, next Monday",
                style=discord.TextStyle.short
            )
        )

    def create_text_modal(self, title: str, label: str, placeholder: str = "", 
                         required: bool = True, max_length: int = 4000,
                         style=discord.TextStyle.paragraph):
        """Helper to create a text input modal"""
        modal = discord.ui.Modal(title=title)
        modal.add_item(discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            required=required,
            max_length=max_length,
            style=style
        ))
        return modal

    def create_objective_modal(self):
        """Helper to create new objective modal"""
        modal = discord.ui.Modal(title="Create Follow-up Objective")
        modal.add_item(discord.ui.TextInput(
            label="New Objective",
            placeholder="Describe the follow-up objective...",
            style=discord.TextStyle.paragraph,
            max_length=2000
        ))
        return modal

    async def archive_callback(self, interaction: Interaction):
        await interaction.response.send_message(
            "✅ Objective has been archived. You can still view it in the history.",
            ephemeral=True
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Verify user has permission to interact with buttons"""
        return True  # Could add permission checks here
    
class ObjectiveListView(View):
    def __init__(self):
        super().__init__(timeout=300)
        
        # Quick Actions Row
        self.add_item(Button(
            style=ButtonStyle.success,
            label="New Objective ➕",
            custom_id="new_objective",
            row=0
        ))
        self.add_item(Button(
            style=ButtonStyle.primary,
            label="Quick Update 📝",
            custom_id="quick_update",
            row=0
        ))
        
        # Filter/Sort Row
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="Active Only 🟢",
            custom_id="filter_active",
            row=1
        ))
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="Completed ✅",
            custom_id="filter_completed",
            row=1
        ))
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="All Objectives 📋",
            custom_id="show_all",
            row=1
        ))
        
        # View Options Row
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="Timeline View 📅",
            custom_id="view_timeline",
            row=2
        ))
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="Progress View 📊",
            custom_id="view_progress",
            row=2
        ))
        self.add_item(Button(
            style=ButtonStyle.secondary,
            label="Team View 👥",
            custom_id="view_team",
            row=2
        ))

    async def button_callback(self, interaction: Interaction):
        """Handle all button interactions"""
        try:
            action = interaction.custom_id
            
            if action == "new_objective":
                await self.show_modal(interaction,
                    "Create New Objective",
                    "new_objective_modal",
                    [{
                        'label': 'Objective Description',
                        'placeholder': 'Describe your objective...',
                        'style': discord.TextStyle.paragraph
                    }]
                )
            
            elif action == "quick_update":
                await self.show_modal(interaction,
                    "Quick Update",
                    "quick_update_modal",
                    [{
                        'label': 'Objective Number',
                        'placeholder': 'Enter objective number',
                        'style': discord.TextStyle.short,
                        'required': True
                    },
                    {
                        'label': 'Update',
                        'placeholder': 'Enter your update...',
                        'style': discord.TextStyle.paragraph
                    }]
                )
            
            elif action.startswith("filter_") or action.startswith("view_"):
                await interaction.response.defer(ephemeral=True)
                # This would be implemented to reload the view with different filters
                await interaction.followup.send(
                    "View will be refreshed with your selected filter!",
                    ephemeral=True
                )
            
            else:
                await interaction.response.send_message(
                    "Feature coming soon! Stay tuned.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again or contact support.",
                ephemeral=True
            )
  
class CompletionView(View):
    """View shown after marking an objective complete"""
    def __init__(self, objective_id: str):
        super().__init__(timeout=300)
        self.objective_id = objective_id

        # Final Update Button
        final_update_btn = Button(
            style=ButtonStyle.primary,
            label="Add Final Update 📝",
            custom_id=f"final_update_{objective_id}",
            row=0
        )
        final_update_btn.callback = self.final_update_callback
        self.add_item(final_update_btn)

        # Create Follow-up Button
        followup_btn = Button(
            style=ButtonStyle.success,
            label="Create Follow-up ➡️",
            custom_id=f"followup_{objective_id}",
            row=0
        )
        followup_btn.callback = self.followup_callback
        self.add_item(followup_btn)

        # Archive Button
        archive_btn = Button(
            style=ButtonStyle.secondary,
            label="Archive & Close 📁",
            custom_id=f"archive_{objective_id}",
            row=0
        )
        archive_btn.callback = self.archive_callback
        self.add_item(archive_btn)

    async def final_update_callback(self, interaction: Interaction):
        modal = discord.ui.Modal(title="Final Progress Update")
        modal.add_item(
            discord.ui.TextInput(
                label="Final Update & Results",
                style=discord.TextStyle.paragraph,
                placeholder="Summarize the final results and any key achievements...",
                required=True,
                max_length=2000
            )
        )
        await interaction.response.send_modal(modal)

    async def followup_callback(self, interaction: Interaction):
        modal = discord.ui.Modal(title="Create Follow-up Objective")
        modal.add_item(
            discord.ui.TextInput(
                label="Follow-up Objective",
                style=discord.TextStyle.paragraph,
                placeholder="What's the next goal building on this success?",
                required=True,
                max_length=2000
            )
        )
        modal.add_item(
            discord.ui.TextInput(
                label="Link to Previous",
                style=discord.TextStyle.short,
                placeholder="How does this build on the completed objective?",
                required=False,
                max_length=200
            )
        )
        await interaction.response.send_modal(modal)

    async def archive_callback(self, interaction: Interaction):
        embed = Embed(
            title="📁 Objective Archived",
            description=f"Objective #{self.objective_id} has been completed and archived.",
            color=Color.green()
        )
        embed.add_field(
            name="What's Next?",
            value="• Use `!list completed` to view completed objectives\n"
                  "• Use `!set_objective` to create a new objective\n"
                  "• Use `!view_progress` to review past achievements",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Update the complete_callback in ObjectiveView
async def complete_callback(self, interaction: Interaction):
    try:
        embed = Embed(
            title="🎉 Objective Completed!",
            description="Congratulations on completing this objective!",
            color=Color.green()
        )
        
        embed.add_field(
            name="Next Steps",
            value="Choose your next action:\n"
                  "• Add a final update summarizing results\n"
                  "• Create a follow-up objective\n"
                  "• Archive and close this objective",
            inline=False
        )

        # Create completion view with follow-up options
        completion_view = CompletionView(self.objective_id)
        
        await interaction.response.send_message(
            embed=embed,
            view=completion_view,
            ephemeral=True
        )
        
        # Update the objective status in the database
        if hasattr(interaction.client, 'db'):
            server_id = str(interaction.guild_id)
            server_goals = interaction.client.db.get_goals(server_id)
            if self.objective_id in server_goals["objectives"]:
                server_goals["objectives"][self.objective_id]["status"] = "completed"
                server_goals["objectives"][self.objective_id]["completed_at"] = str(datetime.datetime.now())
                server_goals["objectives"][self.objective_id]["completed_by"] = str(interaction.user.id)
                interaction.client.db.save_goals(server_id)
                
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error completing objective. Please try again.",
            ephemeral=True
        )
          
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