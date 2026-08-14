"""Stage D: reference entry parsing across citation styles."""
from app.parsing.refparse import parse_entry, split_authors, to_csl


def test_ieee_quoted_title():
    f, conf, issues = parse_entry(
        'D. P. Kingma and J. Ba, "Adam: A method for stochastic optimization," '
        'in Proc. ICLR, 2015, pp. 1-13.')
    assert f.title == "Adam: A method for stochastic optimization"
    assert f.authors == ["Kingma, D. P.", "Ba, J."]
    assert f.year == 2015
    assert conf >= 0.8


def test_apa_year_anchor():
    f, conf, _ = parse_entry(
        "Kingma, D. P., & Ba, J. (2015). Adam: A method for stochastic "
        "optimization. International Conference on Learning Representations.")
    assert f.year == 2015
    assert f.authors[0] == "Kingma, D. P."
    assert "Adam" in (f.title or "")
    assert conf >= 0.8


def test_numbered_plain_given_first():
    # the "Attention Is All You Need" reference style
    f, conf, _ = parse_entry(
        "Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E. Hinton. Layer "
        "normalization. CoRR, abs/1607.06450, 2016.")
    assert f.title == "Layer normalization"
    assert f.authors[0] == "Ba, Jimmy Lei"
    assert f.authors[-1] == "Hinton, Geoffrey E."
    assert f.year == 2016
    assert conf >= 0.8


def test_family_first_full_given_pairs():
    # the Adam-paper (ICLR natbib) style: "Family, Given, Family, Given, and Family, Given."
    f, _, _ = parse_entry(
        "Duchi, John, Hazan, Elad, and Singer, Yoram. Adaptive subgradient "
        "methods for online learning and stochastic optimization. JMLR, 12:2121-2159, 2011.")
    assert f.authors == ["Duchi, John", "Hazan, Elad", "Singer, Yoram"]
    assert "Adaptive subgradient" in (f.title or "")


def test_initials_boundary_before_title():
    f, _, _ = parse_entry(
        "Hinton, G.E. and Salakhutdinov, R.R. Reducing the dimensionality of "
        "data with neural networks. Science, 313(5786):504-507, 2006.")
    assert f.authors == ["Hinton, G.E.", "Salakhutdinov, R.R."]
    assert (f.title or "").startswith("Reducing the dimensionality")
    assert f.year == 2006


def test_short_surname_not_split():
    f, _, _ = parse_entry(
        "Denny Britz, Anna Goldie, Minh-Thang Luong, and Quoc V. Le. Massive "
        "exploration of neural machine translation architectures. CoRR, 2017.")
    assert f.authors[-1] == "Le, Quoc V."
    assert (f.title or "").startswith("Massive exploration")


def test_vancouver_style():
    f, _, _ = parse_entry(
        "Kingma DP, Ba J. Adam: a method for stochastic optimization. "
        "Proceedings of ICLR; 2015.")
    assert f.authors[0].startswith("Kingma")
    assert "Adam" in (f.title or "")


def test_doi_arxiv_url_extraction():
    f, _, _ = parse_entry(
        "Smith, J. (2020). A paper. Journal of Things. "
        "https://doi.org/10.1234/abc.5678")
    assert f.doi == "10.1234/abc.5678"
    f2, _, _ = parse_entry(
        "Zeiler, Matthew D. Adadelta: An adaptive learning rate method. "
        "arXiv preprint arXiv:1212.5701, 2012.")
    assert f2.arxiv_id == "1212.5701"
    assert f2.authors == ["Zeiler, Matthew D."]


def test_et_al_surfaced():
    f, _, issues = parse_entry(
        "Deng, Li, Li, Jinyu, Huang, Jui-Ting, et al. Recent advances in deep "
        "learning for speech research. In ICASSP, 2013.")
    assert f.authors[0] == "Deng, Li"
    assert f.authors[1] == "Li, Jinyu"
    assert any("et al" in i for i in issues)
    assert (f.title or "").startswith("Recent advances")


def test_garbage_flagged_not_dropped():
    f, conf, issues = parse_entry("Published as a conference paper at ICLR 2015")
    assert conf < 0.5
    assert issues                      # problems are reported


def test_year_range_guard():
    f, _, _ = parse_entry(
        "Hinton, G.E. Reducing things. Science, 313(5786):504-507, 2006.")
    assert f.year == 2006              # (5786) must not be taken as a year


def test_split_authors_ampersand_and_semicolons():
    a, _ = split_authors("Kingma, D. P., & Ba, J.")
    assert a == ["Kingma, D. P.", "Ba, J."]
    b, _ = split_authors("Smith, J.; Doe, A.; Roe, R.")
    assert b == ["Smith, J.", "Doe, A.", "Roe, R."]


def test_to_csl_mapping():
    f, _, _ = parse_entry(
        'D. P. Kingma and J. Ba, "Adam: A method," in Proceedings of ICLR, 2015.')
    item = to_csl(f, "ref_9")
    assert item["id"] == "ref_9"
    assert item["type"] == "paper-conference"
    assert item["author"][0] == {"family": "Kingma", "given": "D. P."}
    assert item["issued"] == {"date-parts": [[2015]]}
