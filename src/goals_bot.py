import discord
from discord.ext import commands
from anthropic import Anthropic
import json
import datetime
import os
from discord import Embed
from dotenv import load_dotenv
from .setup_commands import setup_commands

# Load environment variables
load_dotenv()

class GoalsDatabase:
    def __init__(self, filename="goals.json"):
        # Add debug logging
        self.filename = filename
        print(f"Initializing database with file: {self.filename}")
        print(f"Directory contents: {os.listdir('.')}")
        self.goals = self.load_goals()
    
    def load_goals(self) -> dict:
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
        
        super().__init__(command_prefix='!', intents=intents)
        
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.db = GoalsDatabase()
    
    async def setup_hook(self):
        """Set up bot commands"""
        print("Setting up bot commands...")
        setup_commands(self)
        print("Bot commands setup complete")

    async def on_ready(self):
        print(f'Bot is ready and logged in as {self.user}')
        print(f'Connected to {len(self.guilds)} guilds')

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
            print(f"Starting objective implementation for text: {objective_text}")
            message = await self.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                temperature=0.7,
                messages=[{
                    "role": "user",
                    "content": f"""Please structure this business objective into a SMART goal format:..."""
                }]
            )
            print(f"Got response from Anthropic: {message}")
        # try:
        #     message = await self.anthropic.messages.create(
        #         model="claude-3-sonnet-20240229",
        #         max_tokens=1024,
        #         temperature=0.7,
        #         messages=[{
        #             "role": "user",
        #             "content": f"""Please structure this business objective into a SMART goal format:

        #             Objective: {objective_text}
                    
        #             Format your response as:
        #             1. Structured Objective:
        #             [Describe the goal using SMART criteria]

        #             2. Key Metrics:
        #             • [Key metric 1]
        #             • [Key metric 2]
        #             • [etc...]

        #             3. Suggested Timeline:
        #             • [Timeline point 1]
        #             • [Timeline point 2]
        #             • [etc...]"""
        #         }]
        #     )
            
            structured_objective = str(message.content)
            objective_id = str(len(self.db.goals["objectives"]) + 1)
            
            formatted_objective = self.format_section(structured_objective)
            
            embed = Embed(
                title="📋 New Objective Created",
                color=0x00ff00
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
            error_embed = Embed(
                title="❌ Error Setting Objective",
                description=f"An error occurred: {str(e)}",
                color=0xff0000
            )
            await ctx.send(embed=error_embed)
            print(f"Detailed error: {e}")

    async def _list_objectives_impl(self, ctx):
        """Implementation of list command"""
        try:
            if not self.db.goals["objectives"]:
                await ctx.send("No objectives set yet! Use `!set_objective` to create one.")
                return
            
            # Create initial embed
            embed = Embed(
                title="📊 Company Objectives",
                color=0x0088ff,
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
                        color=0x0088ff
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
                color=0xff0000
            )
            await ctx.send(embed=error_embed)
            print(f"Detailed error: {e}")

def main():
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("DISCORD_TOKEN not found in environment variables")
    
    print("Starting bot...")    
    bot = CompanyAssistant()
    try:
        print("Running bot...")
        bot.run(discord_token)
    except Exception as e:
        print(f"Bot crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()