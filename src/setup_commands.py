from discord import Embed
import datetime
from discord.ext import commands

def setup_commands(bot):
    """Set up all bot commands"""
    
    @bot.command(name='test')
    async def test(ctx):
        """Test if the bot is working"""
        await ctx.send("I'm working! 🎉")

    @bot.command(name='set_objective')
    async def set_objective(ctx, *, objective_text):
        """Set a new company objective"""
        # Skip typing indicator in test environment
        if not hasattr(ctx, '_testing'):
            async with ctx.typing():
                await bot._set_objective_impl(ctx, objective_text)
        else:
            await bot._set_objective_impl(ctx, objective_text)

    @bot.command(name='list')
    async def list_objectives(ctx):
        """List all objectives"""
        await bot._list_objectives_impl(ctx)

    @bot.command(name="update_status")
    async def update_objective_status(ctx, objective_id: str, status: str):
        await bot._update_objective_status_impl(ctx, objective_id, status)

    @bot.command(name="delete_objective")
    async def delete_objective(ctx, objective_id: str):
        await bot._delete_objective_impl(ctx, objective_id)

    @bot.command(name="add_progress")
    async def add_progress(ctx, objective_id: str, *, update_text: str):
        await bot._add_progress_impl(ctx, objective_id, update_text)

    @bot.command(name="view_progress")
    async def view_progress(ctx, objective_id: str):
        await bot._view_progress_impl(ctx, objective_id)

    @bot.command(name="clear_all")
    @commands.has_permissions(administrator=True)  # Built-in Discord.py permission check
    async def clear_all(ctx):
        """Clear all objectives (Testing only - Admin required)"""
        # Add confirmation step
        confirm_msg = await ctx.send("⚠️ **WARNING**: This will delete ALL objectives and updates. React with ✅ to confirm.")
        await confirm_msg.add_reaction("✅")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "✅"

        try:
            await bot.wait_for('reaction_add', timeout=30.0, check=check)
            await bot._clear_all_impl(ctx)
        except TimeoutError:
            await ctx.send("Clear all operation cancelled (timed out)")

    @bot.command(name="reset_railway")
    @commands.has_permissions(administrator=True)
    async def reset_railway(ctx):
        """Reset the database file on Railway"""
        await bot._reset_railway_impl(ctx)

    return bot  # Return bot instance with commands added