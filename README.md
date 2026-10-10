# Greenlogy pre Home Assistant

Neoficiálna integrácia pre zákazníkov slovenského dodávateľa elektriny [Greenlogy](https://www.greenlogy.com).
Načíta stav **virtuálnej batérie (Green VBattery)** a **hodinové merania z elektromera** zo zákazníckeho portálu
[portal.greenlogy.com](https://portal.greenlogy.com).

> ⚠️ Greenlogy nemá verejné API. Integrácia používa rovnaké rozhranie ako ich webový portál, ktoré sa môže
> kedykoľvek zmeniť. Nie je to oficiálny produkt Greenlogy.

> 🧪 **Beta (0.1.0)** – integrácia sa práve testuje. Ak niečo nefunguje, založte prosím
> [issue](https://github.com/durcak/ha-greenlogy/issues) aj s logom (bez hesla).

## Čo dostanete

| Senzor | Popis |
|---|---|
| Virtuálna batéria | aktuálny stav nabitia (kWh) |
| Uložené do virtuálnej batérie | energia pripísaná od začiatku ročného obdobia |
| Odobraté z virtuálnej batérie | energia odobratá od začiatku ročného obdobia |
| Odber zo siete včera | podľa elektromera distribútora |
| Dodávka do siete včera | podľa elektromera distribútora |
| Merania k dispozícii do | do kedy sú hodinové merania naimportované |
| Cena elektriny VT / NT | ceny silovej elektriny zo zmluvy |

Okrem senzorov integrácia priebežne importuje **hodinové merania** odberu a dodávky do dlhodobých štatistík HA:

- `greenlogy:grid_import` – odber zo siete
- `greenlogy:grid_export` – dodávka do siete

Pri prvom spustení sa stiahne celá dostupná história. Štatistiky sa dajú zobraziť kartou *Štatistika* alebo
*Graf štatistík*, prípadne použiť na **Energy dashboarde** ako zdroj siete. Distribútor dodáva merania s
oneskorením zvyčajne 1–2 dni, preto sa hodí skôr na mesačné prehľady a porovnanie s faktúrou než na
sledovanie v reálnom čase.

## Inštalácia

### HACS

1. HACS → ⋮ → **Vlastné repozitáre** → pridajte URL tohto repozitára, kategória **Integrácia**.
2. Nainštalujte **Greenlogy** a reštartujte Home Assistant.

### Ručne

Skopírujte priečinok `custom_components/greenlogy` do `config/custom_components/` a reštartujte Home Assistant.

## Nastavenie

**Nastavenia → Zariadenia a služby → Pridať integráciu → Greenlogy** a zadajte e-mail a heslo, ktorými sa
prihlasujete do zákazníckeho portálu Greenlogy. Dáta sa obnovujú každé 3 hodiny.

## Požiadavky

- Home Assistant 2025.4 alebo novší
- účet v zákazníckom portáli Greenlogy (služba virtuálnej batérie je voliteľná – bez nej budú dostupné len merania)

## Licencia

MIT
