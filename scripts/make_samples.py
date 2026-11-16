"""Generates the fictional Turkish sample documents in documents/.

The company, people and numbers are invented. Every page says so. The point
is to have realistic quality-system documents in Turkish, with facts that the
evaluation set can check exactly.

    python scripts/make_samples.py --font /usr/share/fonts/truetype/dejavu
"""

from __future__ import annotations

import argparse
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

COMPANY = "Kuzey Devre Teknolojileri A.Ş."
NOTICE = "Kurgusal örnek belgedir; gerçek bir şirkete ait değildir."

# Each document: code, title, revision, then (heading, paragraphs) sections.
# A "\f" section starts a new page, so facts land on predictable pages.
ESD = (
    "ESD-PR-001",
    "Elektrostatik Boşalma (ESD) Kontrol Prosedürü",
    "Rev. 04, 12.03.2026",
    [
        (
            "1. Amaç ve Kapsam",
            [
                "Bu prosedür, elektrostatik boşalmaya duyarlı (ESDS) elektronik bileşenlerin üretim, depolama ve sevkiyat "
                "sırasında hasar görmesini önlemek için uygulanacak kontrolleri tanımlar. Prosedür, IEC 61340-5-1 standardına "
                "dayanır ve tüm üretim hatlarını, laboratuvarları ve depoyu kapsar.",
                "ESD korumalı alan (EPA), zemininde sarı-siyah şerit bulunan ve girişinde ESD uyarı levhası olan alandır. "
                "EPA'ya ESD eğitimini tamamlamamış hiç kimse refakatsiz giremez.",
            ],
        ),
        (
            "2. Sorumluluklar",
            [
                "ESD koordinatörü Kalite Güvence Müdürlüğü'ne bağlıdır ve programın yıllık değerlendirmesinden sorumludur. "
                "Hat şefleri, vardiya başı kontrollerinin yapıldığını ve kayıt altına alındığını doğrular.",
            ],
        ),
        (
            "3. Bileklik ve Ayakkabı Kontrolleri",
            [
                "Bileklik kayışı, kullanıcıyı 1 MΩ (±%20) seri dirençle topraklama noktasına bağlar. Bu direnç, kullanıcıyı "
                "elektrik çarpmasına karşı korumak için zorunludur ve çıkarılamaz.",
                "Her çalışan, vardiya başında bilekliğini ve ESD ayakkabısını giriş noktasındaki test cihazında test eder. "
                "Sonuç ESD-F-03 Günlük Bileklik Test Formu'na kaydedilir. Testten kalan bileklik kullanılmaz; çalışan yedek "
                "bileklik alır ve durum hat şefine bildirilir.",
            ],
        ),
        ("\f", []),
        (
            "4. Zemin, Masa ve Ortam Koşulları",
            [
                "EPA zemininin ve çalışma masalarının toprağa direnci 10^6 Ω ile 10^9 Ω arasında olmalıdır. Zemin ve masa "
                "ölçümleri üç ayda bir yapılır ve ESD-F-07 formuna kaydedilir.",
                "EPA içindeki bağıl nem %30 ile %70 arasında tutulur. Nem %30'un altına düştüğünde nemlendiriciler "
                "çalıştırılır ve ESD koordinatörü bilgilendirilir.",
                "İyonizerler ayda bir kontrol edilir: 1000 V'tan 100 V'a boşalma süresi 2 saniyeden kısa olmalı, denge "
                "gerilimi ±35 V'u aşmamalıdır.",
            ],
        ),
        (
            "5. Ambalaj ve Taşıma",
            [
                "ESDS bileşenler EPA dışına yalnızca kapalı, ekranlı (metalize) torbalarda veya iletken kasalarda çıkarılır. "
                "Pembe antistatik torbalar yalnızca EPA içinde kullanılabilir; ekranlama sağlamadıkları için sevkiyatta "
                "kullanılmaz.",
            ],
        ),
        (
            "6. Eğitim",
            [
                "Yeni çalışanlar EPA'ya girmeden önce 4 saatlik ESD temel eğitimini tamamlar. Tüm EPA çalışanları 12 ayda bir "
                "tazeleme eğitimi alır. Eğitim kayıtları İnsan Kaynakları tarafından saklanır.",
            ],
        ),
        (
            "7. Uygunsuzluklar",
            [
                "Kontrollerde tespit edilen uygunsuzluklar 24 saat içinde Kalite Güvence'ye bildirilir. ESD kaynaklı olduğundan "
                "şüphelenilen ürün hataları için hata analizi yapılır ve sonuç aylık kalite toplantısında değerlendirilir.",
            ],
        ),
    ],
)

MANUAL = (
    "KAL-EK-01",
    "Kalite El Kitabı",
    "Rev. 09, 05.01.2026",
    [
        (
            "1. Kalite Politikası",
            [
                f"{COMPANY}, müşterilerine zamanında ve hatasız elektronik kart montajı sunmayı, süreçlerini veriyle yönetmeyi "
                "ve sürekli iyileştirmeyi taahhüt eder. Kalite yönetim sistemi ISO 9001:2015 standardına uygundur.",
                "Şirketin kalite hedefleri her yıl Ocak ayında belirlenir. 2026 yılı için müşteri hata oranı hedefi 150 PPM'in "
                "altında, zamanında teslimat hedefi ise %97'nin üzerindedir.",
            ],
        ),
        (
            "2. Yönetimin Gözden Geçirmesi",
            [
                "Yönetimin gözden geçirmesi yılda iki kez, Ocak ve Temmuz aylarında yapılır. Toplantıya genel müdür başkanlık "
                "eder; kalite hedefleri, iç tetkik sonuçları, müşteri şikâyetleri ve tedarikçi performansı değerlendirilir.",
            ],
        ),
        (
            "3. İç Tetkikler",
            [
                "Her süreç yılda en az bir kez tetkik edilir. Tetkikçiler, kendi çalıştıkları süreci tetkik edemez. "
                "Tetkik bulguları için düzeltici faaliyet 30 gün içinde planlanır.",
            ],
        ),
        ("\f", []),
        (
            "4. Müşteri Şikâyetleri",
            [
                "Müşteri şikâyeti alındığında 1 iş günü içinde müşteriye alındı bilgisi verilir. Kök neden analizi 8D "
                "yöntemiyle yapılır ve 8D raporu en geç 10 iş günü içinde müşteriye gönderilir.",
                "Aynı hatanın 12 ay içinde tekrar etmesi durumunda konu yönetimin gözden geçirmesine taşınır.",
            ],
        ),
        (
            "5. Ölçüm Cihazlarının Kalibrasyonu",
            [
                "Ürün kalitesini etkileyen tüm ölçüm cihazları yılda bir kez akredite bir laboratuvarda kalibre edilir. "
                "Kalibrasyonu geçmiş cihazlar kırmızı etiketle işaretlenir ve kullanımdan kaldırılır.",
            ],
        ),
        (
            "6. Doküman Kontrolü",
            [
                "Prosedür ve talimatlar 2 yılda bir gözden geçirilir. Geçerli sürümler yalnızca doküman yönetim sisteminde "
                "tutulur; basılı kopyalar kontrolsüz kopya sayılır.",
            ],
        ),
    ],
)

SUPPLIER = (
    "TED-PR-004",
    "Tedarikçi Seçimi ve Değerlendirme Prosedürü",
    "Rev. 02, 20.06.2025",
    [
        (
            "1. Tedarikçi Sınıfları",
            [
                "Tedarikçiler ürün üzerindeki etkilerine göre üç sınıfa ayrılır. A sınıfı: aktif bileşen, baskılı devre kartı "
                "ve lehim malzemesi tedarikçileri. B sınıfı: pasif bileşen ve mekanik parça tedarikçileri. C sınıfı: ambalaj "
                "ve sarf malzemesi tedarikçileri.",
            ],
        ),
        (
            "2. Tedarikçi Denetimleri",
            [
                "A sınıfı tedarikçiler yılda bir kez, B sınıfı tedarikçiler iki yılda bir yerinde denetlenir. C sınıfı "
                "tedarikçiler yerinde denetlenmez; belgeleri üzerinden değerlendirilir.",
            ],
        ),
        (
            "3. Performans Puanı",
            [
                "Tedarikçi performansı üç ayda bir puanlanır. Puanın %50'si kalite (ret oranı), %30'u teslimat performansı, "
                "%20'si fiyat ve iletişimden oluşur.",
                "Puanı 60'ın altında kalan tedarikçi kırmızı kategoriye alınır ve 30 gün içinde düzeltici faaliyet planı "
                "sunması istenir. Plan sunmayan veya iki dönem üst üste kırmızı kalan tedarikçi onaylı tedarikçi listesinden "
                "çıkarılır.",
            ],
        ),
        ("\f", []),
        (
            "4. Yeni Tedarikçi Onayı",
            [
                "Yeni bir tedarikçi, ilk ürün muayene (FAI) raporu onaylanmadan seri üretim için sipariş alamaz. A sınıfı "
                "adaylar için onaydan önce yerinde denetim zorunludur.",
            ],
        ),
        (
            "5. Giriş Kalite Kontrol",
            [
                "Kritik parçalar için giriş muayenesi AQL 0,65 seviyesinde yapılır; diğer parçalar için AQL 1,5 uygulanır. "
                "Ret edilen partiler için tedarikçiye 48 saat içinde uygunsuzluk raporu gönderilir.",
            ],
        ),
    ],
)

ACTIONS_HEADER = ["Aksiyon No", "Konu", "Sorumlu Birim", "Sorumlu", "Termin", "Durum", "Kaynak"]
ACTIONS = [
    ["AKS-001", "Hat 2 lehim makinesinde köprüleme hatası", "Üretim", "M. Aydın", "15.01.2026", "Kapandı", "Müşteri şikâyeti"],
    ["AKS-002", "Kalibrasyonu geçmiş 3 kumpasın değiştirilmesi", "Kalite Güvence", "S. Kaya", "31.01.2026", "Kapandı", "İç tetkik"],
    [
        "AKS-003",
        "Kondansatör tedarikçisinin kırmızı kategoriye düşmesi",
        "Satın Alma",
        "E. Demir",
        "28.02.2026",
        "Devam ediyor",
        "Tedarikçi puanı",
    ],
    ["AKS-004", "EPA giriş levhalarının yenilenmesi", "Kalite Güvence", "S. Kaya", "15.02.2026", "Kapandı", "ESD denetimi"],
    ["AKS-005", "Depo nem ölçerlerinin kalibrasyonu", "Lojistik", "B. Şahin", "30.03.2026", "Açık", "İç tetkik"],
    ["AKS-006", "Konnektör tedarikçisi için yerinde denetim planı", "Satın Alma", "E. Demir", "30.04.2026", "Açık", "Yeni tedarikçi"],
    ["AKS-007", "8D raporu gecikmesi: müşteri X-201 şikâyeti", "Kalite Güvence", "A. Öztürk", "10.03.2026", "Kapandı", "Müşteri şikâyeti"],
    ["AKS-008", "İyonizer boşalma süresinin 2 sn üzerinde ölçülmesi", "Bakım", "C. Arslan", "20.03.2026", "Devam ediyor", "ESD denetimi"],
    [
        "AKS-009",
        "PCB tedarikçisi ilk ürün muayene (FAI) raporu eksikliği",
        "Satın Alma",
        "E. Demir",
        "15.05.2026",
        "Açık",
        "Yeni tedarikçi",
    ],
    [
        "AKS-010",
        "Yeni çalışanların ESD eğitim kayıtlarının tamamlanması",
        "İnsan Kaynakları",
        "D. Koç",
        "31.03.2026",
        "Kapandı",
        "İç tetkik",
    ],
    [
        "AKS-011",
        "Hat 1 AOI makinesi yanlış ret oranının düşürülmesi",
        "Proses Mühendisliği",
        "K. Yıldız",
        "30.06.2026",
        "Devam ediyor",
        "Verimlilik",
    ],
    [
        "AKS-012",
        "Prosedürlerin 2 yıllık gözden geçirme takvimi",
        "Kalite Güvence",
        "A. Öztürk",
        "31.07.2026",
        "Açık",
        "Yönetimin gözden geçirmesi",
    ],
]


class Document(FPDF):
    def __init__(self, code: str, title: str, revision: str, font_dir: Path):
        super().__init__(format="A4")
        self.code, self.doc_title, self.revision = code, title, revision
        self.add_font("Body", "", str(font_dir / "DejaVuSans.ttf"))
        self.add_font("Body", "B", str(font_dir / "DejaVuSans-Bold.ttf"))
        self.set_margins(20, 22, 20)
        self.set_auto_page_break(True, 22)
        self.set_title(title)
        self.set_author(COMPANY)

    def header(self) -> None:
        self.set_font("Body", "", 8)
        self.set_text_color(110)
        self.cell(0, 5, f"{COMPANY}  |  {self.code}  |  {self.revision}", align="L")
        self.ln(10)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Body", "", 8)
        self.set_text_color(140)
        self.cell(0, 5, f"{NOTICE}   Sayfa {self.page_no()}", align="C")


def write_pdf(spec: tuple, path: Path, font_dir: Path) -> None:
    code, title, revision, sections = spec
    pdf = Document(code, title, revision, font_dir)
    pdf.add_page()
    pdf.set_font("Body", "B", 16)
    pdf.set_text_color(20)
    pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    for heading, paragraphs in sections:
        if heading == "\f":
            pdf.add_page()
            continue
        pdf.set_font("Body", "B", 11)
        pdf.multi_cell(0, 7, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Body", "", 10)
        for text in paragraphs:
            pdf.multi_cell(0, 5.5, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        pdf.ln(2)
    pdf.output(str(path))


def write_actions(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Aksiyonlar"
    ws.append(ACTIONS_HEADER)
    for row in ACTIONS:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")
    for col, width in zip("ABCDEFG", (12, 52, 20, 12, 12, 14, 26), strict=True):
        ws.column_dimensions[col].width = width
    notes = wb.create_sheet("Not")
    notes.append([NOTICE])
    wb.properties.creator = COMPANY
    wb.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, default=Path("/usr/share/fonts/truetype/dejavu"))
    parser.add_argument("--out", type=Path, default=Path("documents"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    write_pdf(ESD, args.out / "ESD-PR-001 ESD Kontrol Proseduru.pdf", args.font)
    write_pdf(MANUAL, args.out / "KAL-EK-01 Kalite El Kitabi.pdf", args.font)
    write_pdf(SUPPLIER, args.out / "TED-PR-004 Tedarikci Degerlendirme.pdf", args.font)
    write_actions(args.out / "Aksiyon Takip Listesi 2026.xlsx")
    print(f"wrote samples to {args.out}")


if __name__ == "__main__":
    main()
