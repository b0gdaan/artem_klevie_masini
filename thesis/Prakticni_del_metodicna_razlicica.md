# Praktični del: preverjanje ponovljivega postopka za vrednotenje SEO

**Status:** metodološka različica za uskladitev z mentorjem. To besedilo ne dokazuje učinka izvedenih SEO-ukrepov na resničnem podjetju. Ni nadomestilo za odobreno dispozicijo ali končno diplomsko nalogo.

## 1. Namen in raziskovalni okvir

Namen praktičnega dela je preveriti, ali je mogoče sestaviti pregleden in ponovljiv postopek za analizo SEO-ukrepov. Postopek povezuje preverjanje podatkov, tehnični pregled HTML, primerjavo obdobij, oceno negotovosti in pripravo poročila. Ločujemo dve vrsti dokazov: dejanski posnetek javno dostopne spletne strani in nadzorovani poskus na sintetičnih podatkih.

Raziskovalno vprašanje metodološke različice je: ali postopek pravilno izračuna opredeljene metrike, zazna vnaprej določene spremembe in ohrani sledljivost rezultatov? Vprašanje, ali določena optimizacija dejansko poveča obisk resničnega spletnega mesta, zahteva dodatne podatke in v tej različici ostaja odprto.

## 2. Podatki in njihovo poreklo

Sintetični posnetek vsebuje 25 izmišljenih strani, razdeljenih v skupine za tehnične, vsebinske, lokalne in dostopnostne ukrepe ter kontrolno skupino. Podatki ne predstavljajo izvoza iz Google Search Console. Naslov primer-finance.test označuje izmišljeno spletišče. Obdobje posnetka je od 1. februarja do 7. septembra 2026. Generator uporablja seme 20260911; statistično ponovno vzorčenje v konfiguraciji smoke uporablja ločeno seme 42.

Generator, konfiguracija in datoteka ground_truth.json omogočajo primerjavo ocen z vnaprej določenimi lastnostmi simulacije. To je prednost za preverjanje programske pravilnosti, ne pa neodvisna potrditev učinkovitosti SEO. Uspeh na podatkih, ki jih ustvari lastni generator, se ne sme neposredno prenesti na resnično spletno mesto.

Drugi vir je en javni odziv HTML strani https://b0gdaan.github.io/artem_klevie_masini/, zajet 11. septembra 2026. Posnetek, datum, status HTTP in kontrolna vsota SHA-256 so shranjeni v reports/public-audit-2026-09-11. Ta vir je resničen, vendar ne vsebuje obiskov, prikazov v iskalniku ali položajev. HTML ni bil obdelan z izvajanjem JavaScripta.

## 3. Metrike in primerjava

Klik pomeni obisk iz rezultata iskanja, prikaz pa pojav povezave v rezultatih po pravilih uporabljenega vira. CTR je razmerje med kliki in prikazi. Povprečni položaj je agregirana metrika, ne stalna uvrstitev strani za eno poizvedbo. Razlaga metrik se opira na dokumentacijo Google Search Console [1].

Za vsako stran in časovno okno izračunamo položaj kot vsoto produktov dnevnega položaja in števila prikazov, deljeno s skupnim številom prikazov. Nato uporabimo logaritem tega povprečja. Strani v nadaljnji primerjavi prispevajo enako težo: uteževanje s prikazi znotraj strani zato ni enako uteževanju celotnega spletišča. Manjši položaj pomeni boljši rezultat. Različica izračuna je did-v2.

Metoda razlike razlik primerja spremembo obravnavane skupine s spremembo kontrolne skupine. Sama primerjava pred ukrepom in po njem lahko zamenja učinek ukrepa s skupnim časovnim trendom. Kontrolna skupina ta problem zmanjša le ob ustreznih predpostavkah: primerljivi trendi brez ukrepa, brez pomembnih prelivanj med skupinami ter brez sočasnih različnih posegov. Metoda teh predpostavk ne zagotavlja samodejno.

Predhodno okno obsega 42 dni in se konča sedem dni pred ukrepom. Po ukrepu izločimo 14 dni uvajalnega obdobja, nato uporabimo 42 dni za vrednotenje. Zahtevamo najmanj 20 dni s prikazi v posameznem oknu. Pri klikih se stopnja računa na koledarski dan, tudi kadar je število prikazov enako nič. Tridnevni zamik razpoložljivosti je nastavitev poskusa, ne zagotovilo o dokončnosti vseh podatkov Search Console.

Pri prilagojenem CTR pričakovane klike ocenimo iz krivulje CTR glede na položaj, naučene samo pred posegi. To zmanjša neposredno mešanje spremembe položaja in spremembe CTR, ne odpravi pa vseh razlik v namenu poizvedb ali prikazu rezultatov.

## 4. Negotovost in preverjanje

Uporabimo 2000 ponovitev skupinskega bootstrap postopka. Ponovno vzorčimo celotne strani, ne posameznih dni, da ohranimo časovno povezanost opazovanj znotraj strani. Ker preverjamo štiri inferenčne hipoteze, odločanje temelji na intervalih z Bonferronijevim popravkom, s stopnjo 98,75 %. Pri petih straneh na skupino je ocena negotovosti omejena; več ponovitev ne nadomesti večjega števila neodvisnih strani.

Za dodatno preverjanje primerjamo model s preprosto primerjavo pred posegom in po njem ter uporabimo navidezni datum posega pred dejanskim datumom v simulaciji. Placebo je diagnostični pregled: morebitni odmik od nič zahteva pojasnilo, ni pa vsak odmik samodejno dokaz napačne izvedbe.

Programski testi vključujejo ročno preverljive izračune, časovna okna, ločitev skupin, determinističnost generatorja in skladnost izvoženih rezultatov. Pri reviziji so bili dodani testi za uteženi položaj, štetje dni s prikazi in zavrnitev izdaje poročila s preskočenimi testi. V izoliranem okolju z odvisnostmi iz requirements.lock je uspelo vseh 53 testov.

## 5. Rezultati sintetičnega poskusa

Vir vseh spodnjih ocen je zagon smoke-20260911T132222Z-72ee40, datoteka metrics/metrics.csv. Vrednosti so zaokrožene; poročilo hrani natančne rezultate.

| Primer | Ocena | Prilagojeni interval | Razlaga v simulaciji |
|---|---:|---:|---|
| H1: tehnični ukrep, položaj | 27,41 % | 26,22 do 29,06 % | Spodnja meja presega simulacijski prag 20 %. |
| H2: vsebinski ukrep, prilagojeni CTR | 19,35 % | 6,92 do 36,41 % | Interval vključuje vrednosti pod pragom 15 %; odločitev je neodločena. |
| H3: lokalni ukrep v primerjavi z vsebinskim | 16,72 % | −28,23 do 68,30 % | Širok interval vključuje nič; prednost ni potrjena. |
| H4: dostopnost, položaj | 0,29 % | −1,88 do 2,11 % | Interval vključuje nič; pozitiven učinek ni potrjen. |
| H5: Domain Authority | +3 točke | Brez inferenčnega intervala | Opisna sprememba v simulaciji; predvideno obdobje še ni končano. |

Podprta H1 pomeni, da je postopek v tem sintetičnem primeru zaznal vnaprej ustvarjeno izboljšanje. Ne pomeni, da tehnični SEO v praksi vedno izboljša položaj za 27 %. Neodločena H2 ni dokaz odsotnosti učinka: podatki ne omogočajo dovolj natančne potrditve zastavljenega praga. Enako pri H4 rezultat blizu nič ne dokazuje splošne nepomembnosti dostopnosti za uporabnike.

## 6. Dejanski pregled javne strani

Strežnik je vrnil status 200. Statični pregled je označil manjkajočo povezavo rel="canonical" in odsotnost prepoznanih strukturiranih podatkov. Canonical lahko pojasni prednostni naslov dokumenta, vendar odsotnost te oznake sama po sebi ne dokazuje težav z indeksiranjem. Strukturirane podatke dodamo samo, če ustrezajo dejanski vsebini; njihova odsotnost ni splošna kršitev pravil.

Pregled ne meri hitrosti v brskalniku, uporabniške izkušnje, popolne skladnosti z WCAG ali spremembe položaja. Prav tako ne predstavlja primerjave pred uvedbo ukrepov in po njej. Kontrolna vsota zajetega HTML je d9bd17c781600e2e234c2a77005622d9693a6964910965aa3bb94e27abdfd529.

## 7. Odprti podatki in nadaljnje delo

HTTP Archive je možen javni vir za razširitev tehničnega dela raziskave [2]. Njegovi podatki opisujejo značilnosti spletnih strani; ne nadomeščajo izvoza Search Console in zgodovine posegov na izbranem spletišču. V tej reviziji zbirka HTTP Archive ni bila prenesena ali vključena v izračune. Navedba vira ni dokaz uporabe podatkov.

Naslednja metodološka razširitev naj vključuje več semen generatorja, ničelne učinke, različne velikosti vzorca, manjkajoče podatke, sezonskost in kršitev primerljivih trendov. Oceniti je treba pogostost lažnih zaznav, pokritost intervalov in odstopanje ocen od znane resnice. Trenutni en sam posnetek in uspešni programski testi takšne obsežne simulacijske validacije še ne nadomeščajo.

Za empirično raziskavo potrebujemo dovoljen izvoz podatkov iz resničnega spletišča, dnevnik dejanskih sprememb ter dovolj dolgo kontrolno in opazovalno obdobje. Pred nadaljevanjem je treba z mentorjem uskladiti, ali naloga ostane raziskava učinkov dejanskega posega ali postane raziskava preverjanja analitičnega postopka.

## 8. Sklep

Praktični prispevek je preverljiv analitični postopek z ločenimi podatkovnimi viri, shranjenimi konfiguracijami, testi in sledljivimi rezultati. Ugotovljene in popravljene programske napake kažejo, zakaj so ročno preverljivi testi pomembni tudi pri prepričljivih grafičnih rezultatih. Dokazi podpirajo delovanje postopka v obravnavanem simulacijskem primeru, ne pa splošnih obljub o rasti obiska.

## Viri

[1] Google. Performance report (Search results): Overview and basic setup. https://support.google.com/webmasters/answer/7576553?hl=en

[2] HTTP Archive. Javni podatki in možnosti dostopa. https://httparchive.org/
