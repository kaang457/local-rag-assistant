from ragassist.bm25 import BM25, tokenize, turkish_lower
from ragassist.chunking import chunk_pages, split_text
from ragassist.loaders import Page, clean


def test_short_text_is_one_chunk():
    assert split_text("Kısa bir paragraf.", 900, 150) == ["Kısa bir paragraf."]


def test_chunks_respect_size_and_overlap():
    text = " ".join(f"Cümle numarası {i} burada biter." for i in range(200))
    pieces = split_text(text, 300, 60)
    assert len(pieces) > 5
    assert all(len(p) <= 300 for p in pieces)
    for a, b in zip(pieces, pieces[1:], strict=False):
        assert b[:20] in a, "consecutive chunks should overlap"


def test_chunks_prefer_sentence_boundaries():
    text = ("Birinci cümle burada bitiyor. " * 20).strip()
    pieces = split_text(text, 200, 40)
    assert all(p.endswith(".") for p in pieces[:-1])


def test_chunks_never_cross_pages():
    pages = [Page("a.pdf", "p. 1", "x " * 600), Page("a.pdf", "p. 2", "y " * 600)]
    chunks = chunk_pages(pages, 300, 50)
    assert {c.location for c in chunks if "x" in c.text} == {"p. 1"}
    assert {c.location for c in chunks if "y" in c.text} == {"p. 2"}
    assert chunks[0].citation == "a.pdf, p. 1"


def test_clean_rejoins_hyphenated_words():
    assert clean("kalibras-\nyon   cihazı") == "kalibrasyon cihazı"


def test_turkish_lowercase():
    assert turkish_lower("IŞIK İzmir") == "ışık izmir"


def test_prefix_stemming_matches_turkish_suffixes():
    assert tokenize("Prosedürü")[0] == tokenize("prosedüründe")[0] == tokenize("PROSEDÜR")[0]


def test_bm25_ranks_the_document_with_the_term_first():
    index = BM25(["Tedarikçi denetimleri yılda bir yapılır.", "Bileklik direnci 1 MΩ olmalıdır.", "Nem aralığı yüzde otuz ile yetmiş."])
    scores = index.scores("tedarikçilerin denetimi")
    assert scores.index(max(scores)) == 0
    assert scores[1] == 0


def test_bm25_handles_codes():
    index = BM25(["AKS-008 iyonizer boşalma süresi", "AKS-003 kondansatör tedarikçisi"])
    scores = index.scores("AKS-003")
    assert scores[1] > scores[0]
