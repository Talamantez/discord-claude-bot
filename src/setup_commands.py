from discord import Embed
import datetime

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

    return bot  # Return bot instance with commands added