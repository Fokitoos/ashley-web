"""Site copy and settings.

Everything in [SQUARE BRACKETS] is a placeholder waiting for real details.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Site:
    name: str = "[Your Name]"
    city: str = "[CITY]"
    email: str = "[YOUR EMAIL]"
    phone: str = "[YOUR PHONE]"
    instagram: str = "[@YOURHANDLE]"
    time_zone: str = "[YOUR TIME ZONE]"
    # Look: accent is any CSS colour; gradient is one of nocturne, dawn, aurora, ember.
    accent: str = "#8E4523"
    gradient: str = "nocturne"


@dataclass(frozen=True, slots=True)
class Slide:
    kind: str  # "Video" or "Photo"
    label: str
    hint: str
    src: str | None = None  # path under /static once the real media exists

    @property
    def is_video(self) -> bool:
        return self.kind == "Video"


@dataclass(frozen=True, slots=True)
class Pillar:
    numeral: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class PortfolioItem:
    title: str
    caption: str
    photo_hint: str
    src: str | None = None


@dataclass(frozen=True, slots=True)
class Offering:
    title: str
    body: str
    detail: str
    price: str = "[PRICE]"


SITE = Site()

SLIDES = (
    Slide(
        "Video",
        "Mini video",
        "A 10 to 20 second loop: slow movement, breath, hands, candlelight. Muted and looping",
    ),
    Slide("Photo", "Portrait", "Seated or standing pose in soft dawn light, 3:4 portrait"),
    Slide("Photo", "Gathering", "A circle on mats with candles and warm faces"),
    Slide("Photo", "Nature", "Practice outdoors, by water or under trees"),
)

PILLARS = (
    Pillar(
        "i.",
        "Gathering",
        "Healing rarely happens alone. In circle, online or in the same room, we practise, "
        "share and sit together, and remember that we are held.",
    ),
    Pillar(
        "ii.",
        "Tending",
        "Yoga for the seasons that ask the most of us: motherhood and grief. Gentle, unhurried "
        "practice that makes room for everything you are carrying.",
    ),
    Pillar(
        "iii.",
        "Releasing",
        "Therapeutic movement to help the body let go of what it has been holding, and oracle "
        "readings for a moment of clarity when the path ahead feels unclear.",
    ),
)

PORTFOLIO = (
    PortfolioItem("Gatherings", "[PLACE, CITY]", "a circle of people gathered on their mats"),
    PortfolioItem(
        "Yoga for mothers",
        "[PLACE OR SERIES NAME]",
        "mothers practising together, little ones nearby",
    ),
    PortfolioItem(
        "Yoga for grief",
        "[PLACE OR SERIES NAME]",
        "a restful pose with blankets and bolsters",
    ),
    PortfolioItem("Oracle readings", "Online or in person", "oracle cards laid out by candlelight"),
    PortfolioItem(
        "Therapeutic movement",
        "[PLACE OR SERIES NAME]",
        "free, expressive movement, eyes closed",
    ),
    PortfolioItem(
        "Circles & ceremonies",
        "[EVENT NAME]",
        "candles, singing bowls, a closing circle",
    ),
)

OFFERINGS = (
    Offering(
        "Gatherings",
        "Circles for practice, sharing and ritual, held online and in person. Come as you are, "
        "and leave feeling a little less alone.",
        "Online & in person · [DATES]",
    ),
    Offering(
        "Yoga for mothers",
        "A nurturing practice for every stage of motherhood. Time to rest, rebuild strength "
        "gently, and be cared for while you care for everyone else.",
        "[FORMAT & SCHEDULE]",
    ),
    Offering(
        "Yoga for grief",
        "Slow, supported movement and breath for times of loss. Nothing to fix and nowhere to "
        "get to, only space for whatever is here today.",
        "[FORMAT & SCHEDULE]",
    ),
    Offering(
        "Oracle readings",
        "An intuitive card reading for reflection and guidance, for when you are standing at a "
        "threshold and want to hear your own inner voice more clearly.",
        "[LENGTH] · online or in person",
    ),
    Offering(
        "Therapeutic movement for release",
        "Gentle, intuitive movement, breath and sound that invite the body to soften and let go "
        "of what it has been holding.",
        "[FORMAT & SCHEDULE]",
    ),
)
