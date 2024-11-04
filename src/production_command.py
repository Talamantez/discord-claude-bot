import datetime
from discord.ext import commands
from discord import Embed

@commands.command(name='set_objective')
async def set_objective_production(ctx, *, objective_text):
    """Set a new company objective (Production version with typing indicator)"""
    async with ctx.typing():
        try:
            message = await ctx.bot.anthropic.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                temperature=0.7,
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
            objective_id = str(len(ctx.bot.db.goals["objectives"]) + 1)
            
            formatted_objective = ctx.bot.format_section(structured_objective)
            
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
            
            ctx.bot.db.goals["objectives"][objective_id] = {
                "text": structured_objective,
                "original_text": objective_text,
                "created_by": str(ctx.author.id),
                "created_at": str(datetime.datetime.now()),
                "status": "active"
            }
            
            ctx.bot.db.save_goals()
            await ctx.send(embed=embed)
            
        except Exception as e:
            error_embed = Embed(
                title="❌ Error Setting Objective",
                description=f"An error occurred: {str(e)}",
                color=0xff0000
            )
            await ctx.send(embed=error_embed)
            print(f"Detailed error: {e}")