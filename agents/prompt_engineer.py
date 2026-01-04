"""
VLTRN SUNO - Prompt Engineer Agent
Handles lyrics generation, style templates, and prompt optimization
"""
import os
import json
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PromptEngineer")

# Try to import anthropic for Claude integration
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed - Claude integration disabled")


@dataclass
class SongPrompt:
    """Structured song prompt for SUNO generation"""
    title: str
    lyrics: str
    style_tags: List[str]
    instrumental: bool = False
    extend_from: Optional[str] = None  # Song ID to extend from

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_tags_string(self) -> str:
        """Format tags for SUNO: [tag1, tag2, tag3]"""
        return "[" + ", ".join(self.style_tags) + "]"


class GenreTemplates:
    """Pre-configured genre templates with optimal tag combinations"""

    TEMPLATES = {
        "pop": {
            "tags": ["pop", "catchy", "upbeat", "radio-friendly"],
            "mood": "energetic and accessible",
            "structure": "verse-prechorus-chorus-verse-chorus-bridge-chorus"
        },
        "hip_hop": {
            "tags": ["hip-hop", "rap", "urban", "bass-heavy"],
            "mood": "confident and rhythmic",
            "structure": "intro-verse-hook-verse-hook-bridge-hook"
        },
        "rock": {
            "tags": ["rock", "electric guitar", "drums", "powerful"],
            "mood": "raw and energetic",
            "structure": "intro-verse-chorus-verse-chorus-solo-chorus"
        },
        "electronic": {
            "tags": ["electronic", "synth", "dance", "EDM"],
            "mood": "pulsing and hypnotic",
            "structure": "intro-buildup-drop-breakdown-buildup-drop-outro"
        },
        "r_and_b": {
            "tags": ["r&b", "soul", "smooth", "groove"],
            "mood": "sensual and emotional",
            "structure": "verse-prechorus-chorus-verse-chorus-bridge-chorus"
        },
        "country": {
            "tags": ["country", "acoustic guitar", "americana", "storytelling"],
            "mood": "heartfelt and sincere",
            "structure": "verse-chorus-verse-chorus-bridge-chorus"
        },
        "jazz": {
            "tags": ["jazz", "swing", "sophisticated", "improvisation"],
            "mood": "cool and complex",
            "structure": "head-solo-solo-head"
        },
        "classical": {
            "tags": ["classical", "orchestral", "cinematic", "dramatic"],
            "mood": "grand and emotional",
            "structure": "intro-theme-development-recapitulation-coda"
        },
        "lo_fi": {
            "tags": ["lo-fi", "chill", "relaxing", "study music"],
            "mood": "mellow and nostalgic",
            "structure": "intro-loop-variation-loop-outro"
        },
        "metal": {
            "tags": ["metal", "heavy", "aggressive", "distorted guitar"],
            "mood": "intense and powerful",
            "structure": "intro-verse-chorus-verse-chorus-breakdown-chorus"
        },
        "indie": {
            "tags": ["indie", "alternative", "dreamy", "atmospheric"],
            "mood": "introspective and artistic",
            "structure": "verse-chorus-verse-chorus-bridge-chorus"
        },
        "gospel": {
            "tags": ["gospel", "spiritual", "uplifting", "choir"],
            "mood": "inspiring and powerful",
            "structure": "verse-chorus-verse-chorus-bridge-vamp"
        }
    }

    @classmethod
    def get_template(cls, genre: str) -> Dict[str, Any]:
        """Get template for a genre"""
        return cls.TEMPLATES.get(genre.lower().replace(" ", "_"), cls.TEMPLATES["pop"])

    @classmethod
    def list_genres(cls) -> List[str]:
        """List all available genres"""
        return list(cls.TEMPLATES.keys())


class MoodModifiers:
    """Mood-based tag modifiers"""

    MOODS = {
        "happy": ["upbeat", "joyful", "bright", "cheerful"],
        "sad": ["melancholic", "emotional", "heartfelt", "bittersweet"],
        "angry": ["aggressive", "intense", "powerful", "raw"],
        "peaceful": ["calm", "serene", "gentle", "soothing"],
        "romantic": ["sensual", "intimate", "passionate", "tender"],
        "nostalgic": ["retro", "vintage", "wistful", "dreamy"],
        "motivational": ["inspiring", "uplifting", "anthemic", "powerful"],
        "dark": ["moody", "atmospheric", "haunting", "mysterious"],
        "party": ["dance", "energetic", "fun", "groovy"],
        "chill": ["relaxed", "laid-back", "mellow", "easy-going"]
    }

    @classmethod
    def get_modifiers(cls, mood: str) -> List[str]:
        """Get tag modifiers for a mood"""
        return cls.MOODS.get(mood.lower(), [])


class VocalProfiles:
    """Vocal style configurations"""

    PROFILES = {
        "female_pop": ["female vocals", "clear", "polished"],
        "female_powerful": ["female vocals", "belting", "powerful"],
        "female_soft": ["female vocals", "breathy", "gentle", "whisper"],
        "male_pop": ["male vocals", "smooth", "clear"],
        "male_deep": ["male vocals", "deep", "baritone"],
        "male_raspy": ["male vocals", "raspy", "gritty"],
        "rapper": ["rap", "rhythmic", "flow"],
        "choir": ["choir", "harmonies", "layered vocals"],
        "duet": ["duet", "male and female vocals", "harmonies"],
        "no_vocals": ["instrumental", "no vocals"]
    }

    @classmethod
    def get_profile(cls, profile: str) -> List[str]:
        """Get vocal tags for a profile"""
        return cls.PROFILES.get(profile.lower().replace(" ", "_"), [])


class PromptEngineer:
    """
    VLTRN SUNO Prompt Engineer
    Generates optimized prompts for SUNO music generation
    """

    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("Claude integration enabled")
        else:
            logger.info("Claude integration disabled - using templates only")

    def generate_lyrics_with_claude(
        self,
        theme: str,
        genre: str = "pop",
        mood: str = "happy",
        additional_instructions: str = ""
    ) -> str:
        """Generate lyrics using Claude AI"""
        if not self.client:
            logger.warning("Claude not available - returning template")
            return self._generate_template_lyrics(theme, genre)

        template = GenreTemplates.get_template(genre)

        prompt = f"""You are a professional songwriter. Write lyrics for a {genre} song about: {theme}

Mood: {mood}
Song structure: {template['structure']}

Requirements:
1. Use SUNO-compatible section tags: [Intro], [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Outro]
2. Keep verses 4-6 lines each
3. Chorus should be catchy and memorable
4. Match the {template['mood']} feel
{additional_instructions}

Write the complete lyrics with section tags:"""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            lyrics = message.content[0].text
            logger.info(f"Generated lyrics for theme: {theme}")
            return lyrics
        except Exception as e:
            logger.error(f"Error generating lyrics with Claude: {e}")
            return self._generate_template_lyrics(theme, genre)

    def _generate_template_lyrics(self, theme: str, genre: str) -> str:
        """Generate simple template lyrics when Claude is not available"""
        return f"""[Verse 1]
Walking through the {theme}
Every moment feels so real
The world is opening up
And I know just how I feel

[Chorus]
This is our time, this is our song
{theme.title()} is where we belong
Singing out loud, singing so strong
Together we can't go wrong

[Verse 2]
The journey continues on
With every step we take
The {theme} guides our way
To the future we will make

[Chorus]
This is our time, this is our song
{theme.title()} is where we belong
Singing out loud, singing so strong
Together we can't go wrong

[Outro]
{theme.title()}... yeah...
"""

    def create_prompt(
        self,
        title: str,
        theme: str,
        genre: str = "pop",
        mood: str = "happy",
        vocal_profile: str = "female_pop",
        instrumental: bool = False,
        custom_tags: Optional[List[str]] = None,
        generate_lyrics: bool = True
    ) -> SongPrompt:
        """Create a complete song prompt for SUNO"""

        # Build style tags
        style_tags = []

        # Add genre tags
        genre_template = GenreTemplates.get_template(genre)
        style_tags.extend(genre_template["tags"])

        # Add mood modifiers
        style_tags.extend(MoodModifiers.get_modifiers(mood))

        # Add vocal profile
        if not instrumental:
            style_tags.extend(VocalProfiles.get_profile(vocal_profile))
        else:
            style_tags.extend(["instrumental", "no vocals"])

        # Add custom tags
        if custom_tags:
            style_tags.extend(custom_tags)

        # Remove duplicates while preserving order
        style_tags = list(dict.fromkeys(style_tags))

        # Generate or use placeholder lyrics
        if generate_lyrics and not instrumental:
            lyrics = self.generate_lyrics_with_claude(theme, genre, mood)
        elif instrumental:
            lyrics = f"[Instrumental]\n{theme}\n[End]"
        else:
            lyrics = ""

        return SongPrompt(
            title=title,
            lyrics=lyrics,
            style_tags=style_tags,
            instrumental=instrumental
        )

    def create_batch_prompts(
        self,
        themes: List[Dict[str, Any]]
    ) -> List[SongPrompt]:
        """Create multiple prompts from a list of theme configurations"""
        prompts = []
        for theme_config in themes:
            prompt = self.create_prompt(
                title=theme_config.get("title", "Untitled"),
                theme=theme_config.get("theme", "life"),
                genre=theme_config.get("genre", "pop"),
                mood=theme_config.get("mood", "happy"),
                vocal_profile=theme_config.get("vocal", "female_pop"),
                instrumental=theme_config.get("instrumental", False),
                custom_tags=theme_config.get("tags", []),
                generate_lyrics=theme_config.get("generate_lyrics", True)
            )
            prompts.append(prompt)
        return prompts

    def save_prompt(self, prompt: SongPrompt, filepath: str):
        """Save a prompt to file"""
        with open(filepath, 'w') as f:
            json.dump(prompt.to_dict(), f, indent=2)
        logger.info(f"Prompt saved to {filepath}")

    def load_prompt(self, filepath: str) -> SongPrompt:
        """Load a prompt from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return SongPrompt(**data)


def main():
    """Test the Prompt Engineer"""
    print("=" * 60)
    print("VLTRN SUNO Prompt Engineer - Test")
    print("=" * 60)

    engineer = PromptEngineer()

    # List available genres
    print("\n[1] Available Genres:")
    for genre in GenreTemplates.list_genres():
        print(f"    - {genre}")

    # Create a test prompt
    print("\n[2] Creating test prompt...")
    prompt = engineer.create_prompt(
        title="Summer Dreams",
        theme="summer vacation and freedom",
        genre="pop",
        mood="happy",
        vocal_profile="female_pop",
        generate_lyrics=True
    )

    print(f"\n    Title: {prompt.title}")
    print(f"    Tags: {prompt.get_tags_string()}")
    print(f"    Instrumental: {prompt.instrumental}")
    print(f"\n    Lyrics:\n{prompt.lyrics[:500]}...")

    # Save the prompt
    print("\n[3] Saving prompt...")
    output_dir = Path(__file__).parent.parent / "templates"
    output_dir.mkdir(exist_ok=True)
    engineer.save_prompt(prompt, str(output_dir / "test_prompt.json"))

    print("\n" + "=" * 60)
    print("Prompt Engineer test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
