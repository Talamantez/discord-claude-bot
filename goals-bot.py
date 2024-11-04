import discord
from discord.ext import commands
from anthropic import Anthropic
import json
import datetime
import os
from discord import Embed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GoalsDatabase:
    def __init__(self, filename="goals.json"):
        self.filename = filename
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
        
        # Get API key from environment variables
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.db = GoalsDatabase()
    
    async def setup_hook(self):
        self.add_commands()
    
    def add_commands(self):
        @self.command(name='test')
        async def test(ctx):
            """Test if the bot is working"""
            await ctx.send("I'm working! 🎉")
        
        @self.command(name='set_objective')
        async def set_objective(ctx, *, objective_text):
            """Set a new company objective"""
            try:
                processing_msg = await ctx.send("Processing your objective...")
                
                try:
                    message = self.anthropic.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=1024,
                        temperature=0.7,
                        messages=[
                            {
                                "role": "user",
                                "content": f"""Please structure this business objective into a SMART goal format 
                                (Specific, Measurable, Achievable, Relevant, Time-bound):
                                
                                Objective: {objective_text}
                                
                                Format your response as:
                                1. Structured Objective:
                                2. Key Metrics:
                                3. Suggested Timeline:"""
                            }
                        ]
                    )
                    
                    structured_objective = message.content
                    if hasattr(structured_objective, 'text'):
                        structured_objective = structured_objective.text
                    else:
                        structured_objective = str(structured_objective)
                    
                    objective_id = str(len(self.db.goals["objectives"]) + 1)
                    
                    self.db.goals["objectives"][objective_id] = {
                        "text": structured_objective,
                        "original_text": objective_text,
                        "created_by": str(ctx.author.id),
                        "created_at": str(datetime.datetime.now()),
                        "status": "active"
                    }
                    
                    self.db.save_goals()
                    
                    embed = Embed(
                        title="📋 New Objective Created", 
                        color=0x00ff00
                    )
                    
                    parts = structured_objective.split('\n\n')
                    for part in parts:
                        if part.strip():
                            title = part.split(':\n')[0].strip()
                            content = part.split(':\n')[1].strip() if ':\n' in part else part
                            embed.add_field(name=title, value=content, inline=False)
                    
                    embed.add_field(
                        name="Original Input", 
                        value=objective_text[:1024],
                        inline=False
                    )
                    embed.set_footer(text=f"Objective ID: {objective_id} | Created by {ctx.author.name}")
                    
                    await processing_msg.delete()
                    await ctx.send(embed=embed)
                    
                except Exception as api_error:
                    await processing_msg.edit(content=f"Error with Claude API: {str(api_error)}")
                    print(f"Detailed API error: {api_error}")
                    
            except Exception as e:
                await ctx.send(f"💥 Error setting objective: {str(e)}\nPlease try again or contact support.")
                print(f"Detailed error: {e}")

        @self.command(name='list')
        async def list_objectives(ctx):
            """List all objectives"""
            try:
                if not self.db.goals["objectives"]:
                    await ctx.send("No objectives set yet! Use `!set_objective` to create one.")
                    return
                
                embed = Embed(title="📊 Company Objectives", color=0x0088ff)
                
                for obj_id, obj in self.db.goals["objectives"].items():
                    value = str(obj["text"])[:1024]
                    embed.add_field(
                        name=f"Objective {obj_id}",
                        value=value,
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(f"Error listing objectives: {str(e)}")

def main():
    # Get Discord token from environment variables
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("DISCORD_TOKEN not found in environment variables")
        
    bot = CompanyAssistant()
    bot.run(discord_token)

if __name__ == "__main__":
    main()