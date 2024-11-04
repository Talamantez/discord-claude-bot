from setuptools import setup, find_packages

setup(
    name="goals-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "discord.py>=2.3.2",
        "anthropic>=0.7.2",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        'test': [
            'pytest>=7.4.0',
            'pytest-asyncio>=0.21.0',
            'pytest-cov>=4.1.0',
        ],
    },
)