import random
import unicodedata

import pytest

from harfix.normalize import ARABIC_LETTERS

# Original text written for these tests (no third-party content).
CLEAN_LINES = [
    "تهدف هذه المكتبة إلى فحص النصوص العربية المستخرجة من ملفات المستندات "
    "قبل إضافتها إلى فهرس البحث",
    "فإذا كانت الحروف صحيحة والترتيب سليما يبقى النص كما هو دون أي تعديل",
    "أما إذا ظهرت حروف مستبدلة أو رموز غير معروفة فإن الصفحة تحال إلى التعرف الضوئي على الحروف",
    "ويعتمد القرار على نموذج إحصائي صغير يقيس مدى احتمال تتابع الحروف في اللغة العربية الفصحى",
    "ويعرض التقرير سبب القرار لكل صفحة ولكل خط حتى يستطيع المراجع التحقق منه بسهولة",
    "وتحفظ الأرقام والجداول كما هي لأن المكتبة لا تعدل النص الأصلي في هذه المرحلة",
]
CLEAN = "\n".join(CLEAN_LINES)


def permute_letters(text: str, seed: int = 7) -> str:
    """Every Arabic letter mapped to another one, like a font with a wrong ToUnicode map."""
    letters = sorted(ARABIC_LETTERS)
    shuffled = letters[:]
    random.Random(seed).shuffle(shuffled)
    table = dict(zip(letters, shuffled, strict=True))
    return "".join(table.get(ch, ch) for ch in text)


def isolated_forms(text: str) -> str:
    """Replace letters with their isolated presentation-form code points."""
    table = {}
    for cp in range(0xFE70, 0xFF00):
        ch = chr(cp)
        if unicodedata.name(ch, "").endswith("ISOLATED FORM"):
            base = unicodedata.normalize("NFKC", ch)
            if len(base) == 1:
                table.setdefault(base, ch)
    return "".join(table.get(ch, ch) for ch in text)


# A pre-Unicode font whose glyphs sit on printable ASCII codes, the way old Arabic
# desktop-publishing fonts did: the text layer extracts as Latin-looking gibberish.
_PRINTABLE = [chr(cp) for cp in range(0x21, 0x7F)]
random.Random(11).shuffle(_PRINTABLE)
ASCII_LEGACY = dict(zip(sorted(ARABIC_LETTERS), _PRINTABLE, strict=False))


def ascii_legacy(text: str) -> str:
    return "".join(ASCII_LEGACY.get(ch, ch) for ch in text)


@pytest.fixture
def clean_text() -> str:
    return CLEAN
