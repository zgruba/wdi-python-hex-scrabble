import time
import re
import sys
import random
from unittest.util import strclass
import numpy as np
from argparse import ArgumentParser, Namespace
from typing import Callable, List, Optional, Tuple, Union
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QPushButton, QLineEdit,
    QMessageBox, QAbstractItemView, QGraphicsScene, QGraphicsView, QLabel,
    QGraphicsSimpleTextItem, QTableWidget, QTableWidgetItem)
from PyQt5.QtGui import QColor, QBrush, QPen, QPolygonF
from PyQt5.QtCore import pyqtSlot, QPointF, Qt
from math import sqrt

POLSKIE_ZNAKI = "ŃńĘęŚśĄąŁłŹźŻżĆćÓó"
# zmienna globalna typu str zbierająca znaki diakrytyczne

MAX_WSPÓŁRZĘDNA = 7
# zmienna globalna do opisu wielkości planszy scrabble

WSPÓŁRZĘDNE = [(x - (y + 1) // 2, y) for x in range(-MAX_WSPÓŁRZĘDNA,
                                                    MAX_WSPÓŁRZĘDNA+1) for y in range(-MAX_WSPÓŁRZĘDNA, MAX_WSPÓŁRZĘDNA+1)]
# lista krotek współrzędnych kafelków na planszy

WSPÓŁRZĘDNE.sort(key=(lambda p: abs(p[0]) + abs(p[1])))
# sortujemy według podanego klucza - przeszukiwanie planszy od (0,0) "promieniście"


class StrMSet:
    # tworzymy klasę multiset str
    def __init__(self, literki: List[str]):
        self.dict = dict()
        for literka in literki:
            self.add(literka)

    def has(self, literka: str) -> bool:
        return literka in self.dict

    def add(self, literka: str):
        if literka not in self.dict:
            self.dict[literka] = 1
        else:
            self.dict[literka] += 1

    def remove(self, literka: str):
        if literka in self.dict:
            if self.dict[literka] == 1:
                self.dict.pop(literka)
            else:
                self.dict[literka] -= 1


class Dostawka:
    # klasa Dostawka - zawiera istotne informacje o dostawce

    KIERUNKI = {"UP": (0, 1), "RIGHT": (1, 0), "DOWN": (1, -1)}
    # kierunki są trzy: UP: (0,1), RIGHT: (1,0), DOWN: (1,-1) zgdodnie z zasadami hex-scrabble

    def __init__(self, słowo: str, start: Tuple[int, int],
                 kierunek: str, współrzędne: Optional[List[Tuple[int, int]]] = None):
        # konstruktor klasy Dostawka

        self.słowo = słowo # słowo, które chcemy utworzyć
        self.start = start # współrzędne startu
        self.wektor = Dostawka.KIERUNKI[kierunek] # kierunek w którym będzie tworzone słowo
        self.litery_od_gracza = StrMSet([]) # litery, które gracz wyłożył z ręki na dostawkę
        if współrzędne is None:
            self.współrzędne = [
                (self.start[0] + i*self.wektor[0],
                 self.start[1] + i*self.wektor[1])
                for i in range(len(self.słowo))
            ]
        else:
            self.współrzędne = współrzędne # ustalamy współrzędne dostawki na planszę

    def czy_dobra(self, plansza: dict) -> bool:
        # sprawdzamy czy dostawka spełnia warunki konieczne: nie wychodzi poza planszę, w przypadku zaczynania
        # przechodzi przez punkt (0,0), czy da się ją dopisać do planszy (mamy punkt zaczepienia)
        # i czy nie jest pusta

        czy_jakaś_nowa = False
        czy_jakaś_pasuje = False
        if not plansza and (0, 0) not in self.współrzędne:
            return False
        for (x, y), literka in zip(self.współrzędne, self.słowo):
            if not (y <= MAX_WSPÓŁRZĘDNA
                    and y >= -MAX_WSPÓŁRZĘDNA
                    and x <= MAX_WSPÓŁRZĘDNA - (y + 1) // 2
                    and x >= -MAX_WSPÓŁRZĘDNA - (y + 1) // 2):
                return False
            if (x, y) in plansza:
                if plansza[(x, y)] != literka:
                    return False
                else:
                    czy_jakaś_pasuje = True
            else:
                czy_jakaś_nowa = True
        return czy_jakaś_nowa and (czy_jakaś_pasuje or not plansza)

    def dodaj_litere(self, litera: str):
        # wykładamy literę na dostawkę

        self.litery_od_gracza.add(litera)

    def dodaj_litery_gracza(self, plansza: dict, litery_gracza: List[str]) -> bool:
        # sprawdzamy czy z liter w ręce da się ułożyć słowo i wyłożyć dostawkę, zapisujemy litery

        litery = StrMSet(litery_gracza)
        for i, punkt in enumerate(self.współrzędne):
            if punkt not in plansza:
                if not litery.has(self.słowo[i]):
                    return False
                else:
                    litery.remove(self.słowo[i])
                    self.dodaj_litere(self.słowo[i])
        return True

    def litery_gracza(self) -> str: 
        # zwracamy wyłożone lietry jako string

        return ''.join([k*v for k, v in self.litery_od_gracza.dict.items()])


class Kafelek:
    # w klasie Kafelek trzymamy rysunek pola hex-scrabble

    RAMKA = QPen(Qt.black)
    WYBRANA_RAMKA = QPen(Qt.green)
    PREMIA_2W = Qt.cyan
    PREMIA_3W = Qt.magenta
    PREMIA_2L = Qt.red
    PREMIA_3L = Qt.blue
    START = QBrush(QColor(209, 204, 255))
    PUSTY = QBrush(QColor(255, 255, 204))
    PEŁNY = QBrush(QColor(255, 204, 229))
    # KOLORY w zależności od funkcji i stanu pola

    def __init__(self, scene: QGraphicsScene, pos: Tuple[int, int],
                 premie_słowne: Optional[str], premie_literowe: dict):
        # konstruktor klasy Kafelek

        poly = QPolygonF([
            QPointF(10, 10), QPointF(10, 15),
            QPointF(10 - 5 * sqrt(3)/2, 17.5), QPointF(10 - 5 * sqrt(3), 15),
            QPointF(10 - 5 * sqrt(3), 10), QPointF(10 - 5 * sqrt(3)/2, 7.5)
        ])
        # tworzenie szcześciokąta na postawie wyznaczających go punków - wierzchołków

        y = -pos[1]
        x = pos[0] + (-y + 1) // 2
        poly.translate(x*10 + (5 * sqrt(3)/2 if (y + 1) % 2 else 0), y*10)
        # ustawiamy kafelek w odpowiedniej pozycji

        self.hexagon = scene.addPolygon(poly, self.RAMKA, self.PUSTY)
        self.hexagon.setScale(4)
        # dodajemy do okna planszy i ustalamy rozmiar kafelków

        self.premia = (f'{premie_słowne}W' if premie_słowne is not None else
                       f'{premie_literowe}L' if premie_literowe is not None else "")
        # sprawdzamy czy to kafelek pola specjalnego

        self.ustaw_premię()
        # ustawiamy premię

        if (pos == (0, 0)):
            self.hexagon.setPen(self.WYBRANA_RAMKA)
            self.hexagon.setBrush(self.START)
        # ustawiamy kolor startu

        self.textItem = QGraphicsSimpleTextItem('', self.hexagon) 
        # str(pos) zamiast '' - żeby zoaczyć jak rozmieszczone są współrzędne

        self.textItem.setScale(0.2)
        # wielkość napisu na kafelku

        self.textItem.setPos((self.hexagon.boundingRect().center()
                              + self.hexagon.boundingRect().topLeft())/2)
        # ustawiamy pozycję tekstu w zależności od prostokąta opisanego/ograniczająego kafelek

        self.litera = None
        self.pos = pos

    def ustaw_premię(self):
        # ustawiamy znaczniki pól specjalnych (są one wyróżnione kolorami ramek)

        if self.premia == "3W":
            self.hexagon.setPen(self.PREMIA_3W)
        elif self.premia == "2W":
            self.hexagon.setPen(self.PREMIA_2W)
        elif self.premia == "3L":
            self.hexagon.setPen(self.PREMIA_3L)
        elif self.premia == "2L":
            self.hexagon.setPen(self.PREMIA_2L)

    def zaznacz(self, zapal: bool):
        # podświetla zaznaczone pole i gasi jeśli nie jest zaznaczone - potrzebne do porusznia się na planszy

        self.hexagon.setPen(self.WYBRANA_RAMKA if zapal else self.RAMKA)
        if not zapal:
            self.ustaw_premię()

    def zmień_literkę(self, literka: str):
        # zmienianie pola tekstowego - do ustawiania literki

        self.textItem.setText(literka)


def punkty(plansza: dict, dostawka: Dostawka,
           premie_literowe: dict, premie_słowne: dict, wartości: dict
           ) -> Tuple[int, List[str]]:
    # punkty trzeba liczyć przed kładzeniem dostawki na planszę - szukamy max

    if dostawka.czy_dobra(plansza):
        # dostawka spełnia warunki konieczne na prawidłową dostawkę

        suma_za_dostawkę = 0
        # robimy możliwe dostawki - trzymamy je w liście dostawki

        dostawki = [dostawka]
        for poz, (x, y) in enumerate(dostawka.współrzędne):
            if (x, y) not in plansza:
                # pole w które chcemy wstawić literkę jest wolne

                for v in [v for v in Dostawka.KIERUNKI.values() if v != dostawka.wektor]:
                    # musimy sprawdzić czy dostawka pasuje, czy po dostawiniu powstaną nowe prawidłowe słowa
                    # na planszy (zajęte)

                    if ((x+v[0], y+v[1]) in plansza) or ((x-v[0], y-v[1]) in plansza):
                        # pola, które nie należą do kierunku dostawiania a stykają się z tym do którego
                        # chcemy dostawić są na planszy (zajęte)

                        słowo = dostawka.słowo[poz]
                        gdzie_jest_start = 0
                        if ((x-v[0], y-v[1]) in plansza):
                            gdzie_jest_start = 1
                            i = 1
                            while (x - i*v[0], y - i*v[1]) in plansza:
                                słowo = plansza[(
                                    x - i*v[0], y - i*v[1])] + słowo
                                i += 1
                            start = (x - (i-1)*v[0], y - (i-1)*v[1])
                        if ((x+v[0], y+v[1]) in plansza):
                            i = 1
                            while (x + i*v[0], y + i*v[1]) in plansza:
                                słowo += plansza[(x + i*v[0], y + i*v[1])]
                                i += 1
                            if not gdzie_jest_start:
                                start = (x, y)
                        # po dostwieniu powstanie ciąg znaków, za pomocą powyższych operacji
                        # chcemy otzrymać współrzędne startu, aby utorzyć dst - nową zmienną klasy Dostawka

                        dst = Dostawka(słowo, start, "RIGHT")
                        dst.wektor = v
                        dostawki.append(dst)

        for dst in dostawki:
            # liczymy punkty za dostawkę - nowoutworzone słowa też się liczą do punktcji

            premia = 1
            suma = 0
            for i, (x, y) in enumerate(dst.współrzędne):
                premia *= premie_słowne.get((x, y), 1)
                try:
                    suma += wartości[dst.słowo[i]] * \
                        premie_literowe.get((x, y), 1)
                except KeyError:
                    # na wypadek błędu klucza

                    return -1, []
            suma_za_dostawkę += premia * suma

        nowesłowa = [
            dst.słowo for dst in dostawki if dst.słowo != dostawka.słowo]
        # lista nowych słów (będziemy je sprawdzać w ruchu komputera - założenie, że gracz uczciwy)

        return suma_za_dostawkę, nowesłowa
    else:
        return -1, []


def wstaw(plansza: dict, dostawka: Dostawka) -> bool:
    # wstawianie dostawki na planszę

    if dostawka.czy_dobra(plansza):
        for (x, y), literka in zip(dostawka.współrzędne, dostawka.słowo):
            plansza[(x, y)] = literka
        return True
    else:
        return False


def ruch_gracza(plansza: dict, dostawka: Dostawka,
                premie_literowe: dict, premie_słowne: dict, wartości: dict) -> int:
    # przeprowadzmy ruch gracza

    pkt, _ = punkty(plansza, dostawka, premie_literowe,
                    premie_słowne, wartości)
    if pkt != -1:
        wstaw(plansza, dostawka)

    return pkt


def ruch(plansza: dict, mojelitery: List[str], kolekcjasłów: set,
         premie_literowe: dict, premie_słowne: dict, wartości: dict, **opcje
         ) -> Union[Dostawka, np.ndarray]:
    # przeprowadzamy ruch komputera

    best = (-1, None)
    if "limit" in opcje and opcje["limit"]:
        # jeśli użytkownik wybrtał poziom trudności w którym komputer ma ograniczony czas
        # zaczynamy mierzyć czas komputerowi na ruch

        start = time.time()
    for słowo in kolekcjasłów:
        # przechodzimy słownik

        if not any([c in mojelitery for c in słowo]):
            # jeśli nie mamy żadnej literki ze słowa to przechodzimy do kolejnego
            # musimy mieć co dostawić

            continue
        for (x, y) in WSPÓŁRZĘDNE:
            # przechodzimy po współrzędnych planszy 

            for kierunek in ["UP", "RIGHT", "DOWN"]:
                # sprawdzamy każdy kierunek

                v = Dostawka.KIERUNKI[kierunek]
                współrzędne = [(x+i*v[0], y+i*v[1]) for i in range(len(słowo))]
                end = (współrzędne[-1][0], współrzędne[-1][1])
                # produkujemy współrzędne kandydata na dostawkę
                
                if plansza.get((x - v[0], y - v[1])) or plansza.get((end[0] + v[0], end[1] + v[1])):
                    # eliminujemy możliwość, że komputer przedłuża słowo bez względu na to co jest
                    # na planszy postawione

                    break
                if not (end[1] <= MAX_WSPÓŁRZĘDNA
                        and end[1] >= -MAX_WSPÓŁRZĘDNA
                        and end[0] <= MAX_WSPÓŁRZĘDNA - (end[1] + 1) // 2
                        and end[0] >= -MAX_WSPÓŁRZĘDNA - (end[1] + 1) // 2):
                        # sprawdzamy czy słowo się mieści na planszy

                    break
                zajęte = [p in plansza for p in współrzędne]
                # lista zajętych współrzędnych z tych do których chcemy dostawiać

                if (not any(zajęte) and plansza) or all(zajęte):
                    # przypadek kiedy chcemy dostawić na puste pola, ale plansza nie jest pusta
                    # (nie mamy jak zaczepić słowa) lub wszystkie z naszych pozycji są zajęte

                    break

                dst = Dostawka(słowo, (x, y), kierunek, współrzędne)
                # tworzymy z tego słowa dostawkę

                pkt, nowesłowa = punkty(
                    plansza, dst, premie_literowe, premie_słowne, wartości)
                # liczymy punkty i dostajemy listę nowych słów, które sprawdzimy
                # czy należą do słownika

                if pkt != -1:
                    # dostawka spełnia warunki konieczne

                    jest_ok = dst.dodaj_litery_gracza(plansza, mojelitery)
                    # da się ułożyć słowo z dostępnych liter

                    if jest_ok and best[0] < pkt:
                        # jeśli dostawka, którą sprawdzmy jest potencjalnie lepsza

                        złe_nowe_słowo = False
                        for nowe in nowesłowa:
                            # sprawdzamy czy nowe słowa to słowa ze słownika

                            if nowe not in kolekcjasłów:
                                złe_nowe_słowo = True
                                break
                        if not złe_nowe_słowo:
                            # jeśli nowe słowa są w słowniku to ustawiamy dostawkę jako najlepszą dotyczas

                            best = (pkt, dst)
            if "limit" in opcje and opcje["limit"] and time.time() - start > opcje["limit"]:
                # kiedy czas się skończył to przerywamy pętlę

                break
    if best[1] != None:
        # jeśli znaleźliśmy dostawkę to ją zwracamy

        return best[1]
    else:
        # jeśli nie znaleźliśmy dostawki zwracamy tablicę liter do wymiany

        return np.random.choice(
            np.array(mojelitery), np.random.randint(1, len(mojelitery) + 1), replace = False
        )
        # losowanie bez zwracania z tablicy literek


def rozgrywka(konfiguracja: dict, imię_gracza: str, trudność: str) -> int:
    # funkcja która przeprowadza rozrywkę w zależności od wprowadzonych danych gracza i konfiguracji

    app = QApplication([])
    App(imię_gracza, konfiguracja, app.processEvents, trudność)
    return app.exec_()


class App(QMainWindow):
    # klasa App kontroluje grę i część wizualizacujną GUI

    def __init__(self, imię_gracza: str, konfiguracja: dict, update_gui: Callable, trudność: str):
        # konstruktor klasy App, ustalamy parametry GUI i parametry gry z konfiguracji

        super().__init__()
        self.title = 'Scrabble'
        self.update_gui = update_gui

        self.left = 150
        self.top = 150
        self.width = 1200
        self.height = 710
        # wymiary okna głównego gry

        self.wynik_komputera = 0
        self.wynik_gracza = 0
        self.imię_gracza = imię_gracza
        self.czy_tura_gracza = random.choice([0, 1])
        # parametry dotyczące wyniku i bieżącej tury -> wyświetlane w GUI

        self.plansza = dict()
        self.kafelki = dict()
        # słowniki do przechowywania kafelków i stanu planszy

        self.kierunek = "RIGHT"
        self.start = (0, 0)
        # domyślnie start w (0,0) i kierunek wpisywania słowa w prawo

        self.woreczek = [
            li for li, _, cz in konfiguracja['worek'] for _ in range(int(cz))
        ]
        self.literki_gracza = [
            random.choice(self.woreczek) for _ in range(konfiguracja['liczba_liter_gracz'])
        ]
        self.literki_komputera = [
            random.choice(self.woreczek) for _ in range(konfiguracja['liczba_liter_gracz'])
        ]
        self.słownik = set([slowo.upper()
                           for slowo in konfiguracja['słownik']])
        self.premie_literowe = konfiguracja['premie_literowe']
        self.premie_słowne = konfiguracja['premie_słowne']
        self.wartości = {literka: int(wart)
                         for literka, wart, _ in konfiguracja['worek']}
        self.limit = 10 if trudność == "ŁATWY" else 20 if trudność == "NORMALNY" else None
        # ustalamy konfigurację gry

        self.initUI()
        # tworzymy okno

        if not self.czy_tura_gracza:
            # losowo grę rozpoczyna albo komputer albo gracz

            self.tura_komputera()

    def initUI(self):
        # tworzymy okno w którym będzie toczyła się gra

        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        # tworzymy okno o ustalonych rozmiarach
        
        self.textbox = QLineEdit(self)
        self.textbox.setValidator(QtGui.QRegExpValidator(
            QtCore.QRegExp(f"[a-zA-Z{POLSKIE_ZNAKI}]+")))
        self.textbox.move(20, 630)
        self.textbox.resize(580, 40)
        # tworzymy skrzynkę tekstową do której gracz będzie wpisywał słowo

        self.button = QPushButton('Dodaj słowo', self)
        self.button.move(20, 670)
        # tworzymy przycisk do dodawania słów

        self.button.clicked.connect(self.textbox_klik)
        # łączymy przycisk z skrzynką tekstową

        self.score1 = QLabel("", self)
        self.score1.resize(300, 20)
        self.score1.move(850, 70)
        self.score2 = QLabel("", self)
        self.score2.resize(300, 20)
        self.score2.move(850, 120)
        self.zmień_wynik()
        # pola tektowe w których będziemy wyświetlać wyniki

        self.tura = QLabel("", self)
        self.tura.resize(300, 20)
        self.tura.move(850, 15)
        myFont=QtGui.QFont()
        myFont.setBold(True)
        self.tura.setFont(myFont)
        self.zmień_turę()
        # pole tektowe w którym będziemy wyświetlać czyja tura

        literki = self.literki_gracza
        self.tableWidget = QTableWidget(len(literki), 2, self)
        self.tableWidget.setHorizontalHeaderLabels(["Literka", "Wartość"])
        self.tableWidget.verticalHeader().hide()
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tableWidget.adjustSize()
        self.tableWidget.setGeometry(820, 200, 330, 400)
        self.set_table(self.wartości)
        # ustalamy tabelkę w której gracz będzie miał literki i będzie mógł wybrać literki do wymiany

        self.button_table = QPushButton('Wymień', self)
        self.button_table.move(820, 610)
        # przycisk wymień do tabelki
        
        self.button_table.clicked.connect(self.tabela_klik)
        # łączymy przycisk z tabelką
        
        scene = QGraphicsScene()
        scene.setBackgroundBrush(QBrush(QColor(255, 229, 204)))
        # rysowanie pola w którym wyświetli się plansza do gry

        for punkt in WSPÓŁRZĘDNE:
            # łączymy punkt z odpowiednim kafelkiem na planszy

            self.kafelki[punkt] = Kafelek(scene, punkt, self.premie_słowne.get(
                punkt, None), self.premie_literowe.get(punkt, None))
        
        view = QGraphicsView(scene, self)
        view.setGeometry(10, 10, 800, 610)
        # ustawiamy pole w oknie 

        view.keyPressEvent = self.keyPressEvent_
        # akcja po wciśnięciu odpowiedniego przycisku z klawiatury

        view.focusInEvent = self.repaint
        # aktualne kafelki będą zapalone po fokusie na pole z kafelkami

        self.show()

    def repaint(self, _):
        # zapala kafelki których pola ma zająć dostawka i gasi pozostałe

        for punkt in WSPÓŁRZĘDNE:
            self.kafelki[punkt].zaznacz(False)
        self.zapal()

    def zmień_wynik(self):
        # aktualizuje wyniki graczy

        self.score1.setText(f"Komputer: {self.wynik_komputera}")
        self.score2.setText(f"{self.imię_gracza}: {self.wynik_gracza}")

    def zmień_turę(self):
        # aktualizuje napis czyja tura

        self.czy_tura_gracza = not self.czy_tura_gracza
        self.tura.setText(
            f"Tura {self.imię_gracza if self.czy_tura_gracza else 'Komputera'}")

    @pyqtSlot() # dektorator łączy sygnał przycisku skrzynki tekstowej z funkcją textbox_klik()
    def textbox_klik(self):
        # wciskając przycisk chcemy dodać słowo na planszę

        słowo = self.textbox.text().upper()
        # chcemy wielkie litery bo na takich działamy w słownikach (domyślnie w konfiguracji)

        dst = Dostawka(słowo, self.start, self.kierunek)
        if not dst.dodaj_litery_gracza(self.plansza, self.literki_gracza):
            QMessageBox.question(
                self, 'Uwaga', "Wpisano złe słowo - błąd ręki", QMessageBox.Ok, QMessageBox.Ok)
            return
        # sprawdzamy czy gracz ma w ręce to co chce wpisać

        points = ruch_gracza(
            self.plansza, dst, self.premie_literowe, self.premie_słowne, self.wartości)
        if points == -1:
            QMessageBox.question(
                self, 'Uwaga', "Wpisano złe słowo - błąd warunki konieczne", QMessageBox.Ok, QMessageBox.Ok)
            return
        # sprawdzamy czy dostawka spełnia watunki konieczne

        self.zgaś(self.kierunek)
        self.połóż(dst, self.premie_literowe, self.premie_słowne)
        self.wynik_gracza += points
        self.zmień_wynik()
        # aktualizujemy okno po dodaniu słowa

        lgracza = dst.litery_gracza()
        self.wymień_litery(
            [x for x in range(len(self.literki_gracza))
             if self.literki_gracza[x] in lgracza],
            self.literki_gracza)
        # uzupełniamy braki w literach

        self.textbox.setText("")
        self.tura_komputera()
        # usuwamy tekst ze skrzynki i zmieniamy turę

    def połóż(self, dostawka: Dostawka,
              premie_literowe: dict, premie_słowne: dict):
        # kładziemy lietrki na planszy

        for punkt, litera in zip(dostawka.współrzędne, dostawka.słowo):
            self.kafelki[punkt].zmień_literkę(litera)
            self.kafelki[punkt].hexagon.setBrush(self.kafelki[punkt].PEŁNY)
            for wspol in premie_literowe:
                if punkt == wspol and premie_literowe[wspol] == 2:
                    self.kafelki[punkt].hexagon.setBrush(
                        self.kafelki[punkt].PREMIA_2L)
                if punkt == wspol and premie_literowe[wspol] == 3:
                    self.kafelki[punkt].hexagon.setBrush(
                        self.kafelki[punkt].PREMIA_3L)
            for wspol in premie_słowne:
                if punkt == wspol and premie_słowne[wspol] == 2:
                    self.kafelki[punkt].hexagon.setBrush(
                        self.kafelki[punkt].PREMIA_2W)
                if punkt == wspol and premie_słowne[wspol] == 3:
                    self.kafelki[punkt].hexagon.setBrush(
                        self.kafelki[punkt].PREMIA_3W)
        # pola specjalne kiedy mają lietrkę wypełniają się kolorkiem z ramki
        # aby gracz wiedział, że to pola specjalne, bo premia nie znika

    def set_table(self, wartości: dict):
        # ustawiamy lietrki w tabelce

        literki = self.literki_gracza
        for i in range(len(literki)):
            self.tableWidget.setItem(i, 0, QTableWidgetItem(literki[i]))
            self.tableWidget.setItem(
                i, 1, QTableWidgetItem(str(wartości[literki[i]])))

    def wymień_litery(self, idx_do_wyjęcia: List[int], ręka: List[str],
                      literki: List[str] = [], wymiana: bool = False):
        # funkcja służy do wymiany liter

        indeksy = np.random.choice(
            np.array(range(len(self.woreczek))), len(idx_do_wyjęcia), replace=False)
        # tablica losowych liter z woreczka o długości listy indeksów do wyjęcia

        for i, idx in zip(idx_do_wyjęcia, indeksy):
            # dobieramy do ręki

            ręka[i] = self.woreczek[idx]
        if wymiana:
            j = 0
            for i in range(len(self.woreczek)):
                if i in indeksy:
                    self.woreczek[i] = literki[j]
                    j += 1
        else:
            self.woreczek = [self.woreczek[i]
                             for i in range(len(self.woreczek)) if i not in indeksy]
        # zmiana która następuje w woreczku po wymianie

        self.set_table(self.wartości)
        # ustawiamy literki wraz z wartościami w tabelce

    @pyqtSlot() # dektorator łączy sygnał przycisku tabelki z funkcją table_klik()
    def tabela_klik(self):
        # klikamy wymień i wymieniamy lietrki w tabelce

        self.zgaś(self.kierunek)
        literki = [item.text()
                   for item in self.tableWidget.selectedItems() if item.column() == 0]
        self.wymień_litery(
            [item.row() for item in self.tableWidget.selectedItems()
             if item.column() == 0],
            self.literki_gracza,
            literki,
            True)
        self.tura_komputera()
        # zmieniamy turę na turę komputera

    def tura_komputera(self):
        # funkcja która przeprowadza turę komputera

        if self.czy_tura_gracza:
            self.zmień_turę()
        # zmieniamy napis czyja tura i int który wskazuje czy tura gracza

        self.update_gui()
        # aktualizujemy okno z nowymi informacjami

        ret = ruch(self.plansza, self.literki_komputera, self.słownik,
                   self.premie_literowe, self.premie_słowne, self.wartości, limit=self.limit)
        # wykomujemy ruch komputera -> zwraca dostawkę bądź tablicę liter do wymiany

        if isinstance(ret, Dostawka):
            # sprawdzamy czy ret jest typu Dostawka

            self.połóż(ret, self.premie_literowe, self.premie_słowne)
            # kładziemy dostawkę na planszę (wizualnie)

            self.wynik_komputera += punkty(
                self.plansza, ret, self.premie_literowe, self.premie_słowne, self.wartości)[0]
            # liczymy komputerowi punkty

            wstaw(self.plansza, ret)
            # wstawiamy literki na planszę (słownik)

            self.zmień_wynik()
            # zmieniamy wynik w oknie

            lgracza = ret.litery_gracza()
            self.wymień_litery(
                [x for x in range(len(self.literki_komputera))
                 if self.literki_komputera[x] in lgracza],
                self.literki_komputera)
            # uzupełnimy rękę komputera

        else:
            # jesteśmy w else - czyli ret to tablica liter do wymiany

            indeksy = []
            tret = ret.copy()
            # kopiujemy tablicę

            for i in range(len(self.literki_komputera)):
                if self.literki_komputera[i] in tret:
                    indeksy.append(i)
                    tret[np.where(tret == self.literki_komputera[i])[0][0]] = ""
                    # w ręce może być kilka takich samych literek a potrzebujemy wymienić dokładnie tyle
                    # ile pojawiło się w tablicy

            for i in indeksy: print(self.literki_komputera[i])
            self.wymień_litery(indeksy, self.literki_komputera, ret, True)
            # wymieniamy literki

        self.zmień_turę()
        # zmieniamy turę w oknie

    def keyPressEvent_(self, a0: QtGui.QKeyEvent) -> None:
        # funkcja obsługuje przyciski z klawiatury
        # manipulujemy nimi pola podświetlane do których chcielibyśmy wpisać dostawkę

        zmiana = False
        nowy_start = self.start
        kierunek = self.kierunek
        if a0.key() == Qt.Key_Up:
            if (self.start[0], self.start[1] + 1) in WSPÓŁRZĘDNE:
                zmiana = True
                nowy_start = (self.start[0], self.start[1] + 1)
        elif a0.key() == Qt.Key_Right:
            if (self.start[0] + 1, self.start[1]) in WSPÓŁRZĘDNE:
                zmiana = True
                nowy_start = (self.start[0] + 1, self.start[1])
        elif a0.key() == Qt.Key_Down:
            if (self.start[0], self.start[1] - 1) in WSPÓŁRZĘDNE:
                zmiana = True
                nowy_start = (self.start[0], self.start[1] - 1)
        elif a0.key() == Qt.Key_Left:
            if (self.start[0] - 1, self.start[1]) in WSPÓŁRZĘDNE:
                zmiana = True
                nowy_start = (self.start[0] - 1, self.start[1])
        # strzałkami poruszamy się po planszy

        elif a0.key() == Qt.Key_Space:
            zmiana = True
            if self.kierunek == "RIGHT":
                self.kierunek = "DOWN"
            elif self.kierunek == "DOWN":
                self.kierunek = "UP"
            else:
                self.kierunek = "RIGHT"
        # spacją zmieniamy kierunek wpisywania kodu

        if zmiana:
            # gasimy i zapalamy wtedy kiedy naciśnie dopuszczalne przyciski z klawiatury

            self.zgaś(kierunek)
            self.start = nowy_start
            self.zapal()

        return super().keyPressEvent(a0)

    def zgaś(self, kierunek: str):
        # gasimy podświetlone kafelki, kierunek po to, żeby zgasić w odpowienim kierunku

        słowo = self.textbox.text()
        for punkt in [self.start] + Dostawka(słowo, self.start, kierunek).współrzędne:
            if punkt in WSPÓŁRZĘDNE:
                self.kafelki[punkt].zaznacz(False)

    def zapal(self):
        # zapalamy kafelki

        słowo = self.textbox.text()
        for punkt in [self.start] + Dostawka(słowo, self.start, self.kierunek).współrzędne:
            if punkt in WSPÓŁRZĘDNE:
                self.kafelki[punkt].zaznacz(True)


def init_parser() -> ArgumentParser:
    # tworzymy parser

    parser = ArgumentParser(
        description="Gra Scrabble na hexagonalnej planszy. Gracz vs komputer.")
    parser.add_argument("-I", dest='imię_gracza',
                        help="Wybrane imię gracza realnego")
    parser.add_argument("-S", dest='plik_ze_slownikiem',
                        help="Ścieżka do pliku tekstowego ze słownikiem dla komputera")
    parser.add_argument("-c", dest='konfiguracja',
                        help="Ścieżka do pliku tekstowego z odpowiednią sformatowaną konfiguracją")
    parser.add_argument("-d", dest='trudność', choices=["ŁATWY", "NORMALNY", "TRUDNY"], default="ŁATWY",
                        help="Ustawienie poziomu trudności. Domyślnie: ŁATWY")
    # dodajemy argumenty porzebne do odpalenia gry

    return parser


def init_config(args: Namespace) -> dict:
    # czytamy konfigurację z pliku konfiguracyjnego

    regex = r'(-?\d+), (-?\d+)'
    # wyrażenie regularne do pobierania współrzędnych

    with open(args.plik_ze_slownikiem, encoding='UTF-8') as file:
        slownik = file.read().split()
    with open(args.konfiguracja, encoding='UTF-8') as konfig:
        lista_do_konfiguracji = konfig.read().splitlines()
    # otwieramy słownik i plik konfiguracyjny
    # odpowiednio tworzymy listę słów i listę linii z odpowiednimi parametrami

    liczba_w_ręce = int(re.findall(r'(\d+)', lista_do_konfiguracji[0])[0])
    PREMIA_2LS = re.findall(regex, lista_do_konfiguracji[1])
    PREMIA_3LS = re.findall(regex, lista_do_konfiguracji[2])
    PREMIA_2WS = re.findall(regex, lista_do_konfiguracji[3])
    PREMIA_3WS = re.findall(regex, lista_do_konfiguracji[4])
    KOSTKI = re.findall(
        fr"'([a-zA-Z{POLSKIE_ZNAKI}])', (\d+), (\d+)", lista_do_konfiguracji[5])
    # re.findall zwraca listy krotek

    premie_literowe = {(int(x), int(y)): 2 for x, y in PREMIA_2LS} | {
        (int(x), int(y)): 3 for x, y in PREMIA_3LS}
    premie_słowne = {(int(x), int(y)): 2 for x, y in PREMIA_2WS} | {
        (int(x), int(y)): 3 for x, y in PREMIA_3WS}
    # łączymy dwa słowniki do premii: literowych i słownych

    return {
        'słownik': slownik,
        'liczba_liter_gracz': liczba_w_ręce,
        'premie_słowne': premie_słowne,
        'premie_literowe': premie_literowe,
        'worek': KOSTKI
    }
# dostajemy konfigurację w postacji słownika

if __name__ == '__main__':
    # w mainie uruchamiamy grę
    
    args = init_parser().parse_args()
    konfiguracja = init_config(args)
    sys.exit(rozgrywka(konfiguracja, args.imię_gracza, args.trudność))
