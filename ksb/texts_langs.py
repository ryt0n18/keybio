"""Textos para escribir en francés, alemán, italiano, portugués, catalán, gallego y euskera.

Siguen las mismas reglas que los de texts.py: los de registro y los de comprobación son
distintos, todos tienen mayúsculas, comas y puntos, y las frases de acceso rondan los 100
caracteres. Se evitan caracteres que la comparación no pliega y que no todos los teclados
escriben con facilidad (ß, œ, l·l).
"""

from __future__ import annotations

FR = {
    "enroll": {
        "FR-R1": ("Le train du matin est parti avec un peu de retard. Par la fenêtre, on voyait des champs de "
                  "blé, de petits villages et quelques routes vides. Marie a ouvert son carnet et a commencé "
                  "une liste de choses à faire. Appeler son frère, revoir le budget et acheter du pain."),
        "FR-R2": ("Quand nous sommes arrivés au port, le vent soufflait fort et les mouettes volaient bas. Un "
                  "pêcheur nous a expliqué que la mer était trop agitée pour sortir. Nous avons pris un café "
                  "au bar du coin. En fin d'après-midi, le ciel s'est dégagé et nous avons pu monter à bord."),
        "FR-R3": ("La bibliothèque du quartier ouvre tous les jours de neuf heures à vingt heures. Elle a une "
                  "salle d'étude silencieuse, des ordinateurs pour consulter le catalogue et un grand rayon "
                  "pour les enfants. Le samedi, elle organise des ateliers de lecture et invite un auteur."),
        "FR-R4": ("Pour préparer une bonne soupe de légumes, il faut du temps et un feu doux. D'abord, on "
                  "épluche les carottes et les pommes de terre, puis on les coupe en petits morceaux. Ensuite, "
                  "on ajoute un oignon. Enfin, on verse de l'eau, du sel et un peu de poivre."),
        "FR-R5": ("Hier soir, il y a eu un orage impressionnant. Les éclairs illuminaient toute la vallée et "
                  "le tonnerre faisait trembler les vitres. Le courant a été coupé pendant presque deux "
                  "heures, alors nous avons allumé des bougies et joué aux cartes dans le salon."),
    },
    "verify": {
        "FR-V1": ("Le dimanche, mon grand-père se lève très tôt pour aller au marché. Il connaît tous les "
                  "commerçants et discute longtemps avec chacun d'eux. Il revient toujours avec des fruits de "
                  "saison, un journal et un gros pain de campagne, puis il prépare le déjeuner."),
        "FR-V2": ("La réunion de lundi a duré plus longtemps que prévu. Nous avons parlé du nouveau projet, du "
                  "calendrier et du budget pour l'année prochaine. Pour finir, Claire a proposé d'organiser "
                  "une petite fête pour l'anniversaire de l'entreprise, et tout le monde a accepté."),
        "FR-V3": ("Il y a quelques années, j'ai décidé d'apprendre à jouer de la guitare. Au début, j'avais "
                  "mal aux doigts et les accords sonnaient très mal, mais je m'entraînais un peu chaque soir. "
                  "Aujourd'hui, je joue plusieurs chansons entières et je chante même avec mes amis."),
    },
    "access": {
        "FR-A1": "Avant de partir, Lucie a fermé les fenêtres, éteint la radio et laissé un mot sur la table.",
        "FR-A2": "Le bus de huit heures avait du retard, alors nous sommes allés à pied jusqu'à la place du marché.",
        "FR-A3": "Chaque dimanche, le boulanger du quartier prépare une tarte aux pommes qui part avant midi.",
        "FR-A4": "Pendant la randonnée, nous avons vu un cerf, traversé un pont en bois et mangé au bord du lac.",
        "FR-A5": "Si le train est encore en retard, nous prendrons un taxi jusqu'à l'hôtel pour y dîner rapidement.",
        "FR-A6": "La boutique du coin vend des fruits frais, les journaux du jour et de bons biscuits maison.",
    },
}

DE = {
    "enroll": {
        "DE-R1": ("Der Zug am Morgen fuhr mit etwas Verspätung ab. Durch das Fenster sah man Weizenfelder, "
                  "kleine Dörfer und ein paar leere Wege. Anna öffnete ihr Notizbuch und begann eine Liste. "
                  "Sie wollte ihren Bruder anrufen, das Budget prüfen und vor dem Heimweg Brot kaufen."),
        "DE-R2": ("Als wir am Hafen ankamen, wehte ein starker Wind und die Möwen flogen tief. Ein Fischer "
                  "erklärte uns, dass das Meer zu unruhig sei, um hinauszufahren. Wir tranken einen Kaffee in "
                  "der Bar an der Ecke. Am Nachmittag klarte der Himmel auf, und wir gingen an Bord."),
        "DE-R3": ("Die Bibliothek im Viertel ist jeden Tag von neun bis acht Uhr geöffnet. Es gibt einen "
                  "ruhigen Lesesaal, Computer für den Katalog und eine gute Abteilung für Kinder. Samstags "
                  "finden dort Lesekurse statt, und einmal im Monat kommt ein bekannter Autor zu Besuch."),
        "DE-R4": ("Für eine gute Gemüsesuppe braucht man Zeit und eine kleine Flamme. Zuerst schält man die "
                  "Karotten und die Kartoffeln, dann schneidet man sie in kleine Stücke. Danach brät man sie "
                  "kurz mit einer Zwiebel an. Zum Schluss gibt man Wasser, Salz und etwas Pfeffer dazu."),
        "DE-R5": ("Gestern Abend gab es ein beeindruckendes Gewitter. Die Blitze erhellten das ganze Tal, und "
                  "der Donner brachte die Fenster zum Zittern. Der Strom fiel fast zwei Stunden lang aus, also "
                  "zündeten wir Kerzen an und spielten im Wohnzimmer Karten. Heute Morgen lagen überall Äste."),
    },
    "verify": {
        "DE-V1": ("Am Sonntag steht mein Opa sehr früh auf, um auf den Markt zu gehen. Er kennt alle Händler "
                  "und unterhält sich lange mit jedem von ihnen. Er kommt immer mit frischem Obst, einer "
                  "Zeitung und einem runden Bauernbrot zurück und kocht dann das Mittagessen."),
        "DE-V2": ("Die Besprechung am Montag dauerte länger als geplant. Wir sprachen über das neue Projekt, "
                  "den Zeitplan und das Budget für das nächste Jahr. Zum Schluss schlug Laura vor, eine kleine "
                  "Feier zum Jubiläum der Firma zu organisieren, und alle waren einverstanden."),
        "DE-V3": ("Vor ein paar Jahren habe ich beschlossen, Gitarre spielen zu lernen. Am Anfang taten mir "
                  "die Finger weh und die Akkorde klangen furchtbar, aber ich habe jeden Abend ein wenig "
                  "geübt. Heute kann ich mehrere Lieder spielen und singe manchmal mit Freunden."),
    },
    "access": {
        "DE-A1": "Bevor sie ging, schloss Lucia die Fenster, machte das Radio aus und legte einen Zettel hin.",
        "DE-A2": "Der Bus um acht Uhr kam zu spät, also liefen wir zum Marktplatz, als es gerade zu regnen begann.",
        "DE-A3": "Jeden Sonntag backt der Bäcker im Viertel einen Apfelkuchen, der schon mittags ausverkauft ist.",
        "DE-A4": "Bei der Wanderung sahen wir einen Hirsch, gingen über eine Holzbrücke und rasteten am See.",
        "DE-A5": "Wenn der Zug wieder Verspätung hat, nehmen wir ein Taxi zum Hotel und essen dort eine Kleinigkeit.",
        "DE-A6": ("Der kleine Laden an der Ecke verkauft frisches Obst, die Zeitungen des Tages und sehr "
                  "leckere Kekse."),
    },
}

IT = {
    "enroll": {
        "IT-R1": ("Il treno del mattino è partito con un po' di ritardo. Dal finestrino si vedevano campi di "
                  "grano, piccoli paesi e qualche strada deserta. Marta ha aperto il quaderno e ha scritto una "
                  "lista di cose da fare: chiamare il fratello, controllare i conti e comprare il pane."),
        "IT-R2": ("Quando siamo arrivati al porto, il vento soffiava forte e i gabbiani volavano bassi. Un "
                  "pescatore ci ha spiegato che il mare era troppo agitato per uscire. Abbiamo preso un caffè "
                  "al bar dell'angolo. Nel pomeriggio, finalmente, il cielo si è aperto e siamo saliti sulla "
                  "barca."),
        "IT-R3": ("La biblioteca del quartiere è aperta tutti i giorni dalle nove alle venti. Ha una sala "
                  "studio silenziosa, alcuni computer per il catalogo e una sezione per bambini molto ricca. "
                  "Il sabato organizza laboratori di lettura e, una volta al mese, invita uno scrittore."),
        "IT-R4": ("Per preparare un buon minestrone servono pazienza e fuoco basso. Prima si sbucciano le "
                  "carote e le patate, poi si tagliano a pezzetti. Dopo si fanno rosolare con una cipolla. "
                  "Alla fine si aggiungono acqua, sale e un filo d'olio, e si lascia cuocere per un'ora."),
        "IT-R5": ("Ieri sera c'è stato un temporale impressionante. I lampi illuminavano tutta la valle, e i "
                  "tuoni facevano tremare i vetri. La corrente è mancata per quasi due ore, così abbiamo "
                  "acceso alcune candele e abbiamo giocato a carte in salotto. Stamattina, le strade erano "
                  "piene di rami."),
    },
    "verify": {
        "IT-V1": ("La domenica mio nonno si alza prestissimo per andare al mercato. Conosce tutti i venditori "
                  "e chiacchiera a lungo con ognuno di loro. Torna sempre con la frutta di stagione, il "
                  "giornale e una grossa pagnotta, e poi prepara il pranzo per tutta la famiglia."),
        "IT-V2": ("La riunione di lunedì è durata più del previsto. Abbiamo parlato del nuovo progetto, del "
                  "calendario e del bilancio per l'anno prossimo. Alla fine Laura ha proposto di organizzare "
                  "una piccola festa per l'anniversario dell'azienda, e tutti hanno accettato."),
        "IT-V3": ("Qualche anno fa ho deciso di imparare a suonare la chitarra. All'inizio mi facevano male le "
                  "dita e gli accordi suonavano malissimo, ma mi esercitavo un po' ogni sera. Adesso so "
                  "suonare diverse canzoni e, ogni tanto, canto perfino insieme ai miei amici."),
    },
    "access": {
        "IT-A1": "Prima di uscire, Lucia ha chiuso le finestre, ha spento la radio e ha lasciato un biglietto.",
        "IT-A2": "L'autobus delle otto era in ritardo, così siamo andati a piedi fino alla piazza del mercato.",
        "IT-A3": "Ogni domenica il fornaio del quartiere prepara una torta di mele che finisce prima di pranzo.",
        "IT-A4": "Durante la gita abbiamo visto un cervo, attraversato un ponte di legno e mangiato al lago.",
        "IT-A5": "Se il treno ritarda ancora, prenderemo un taxi fino all'albergo e ceneremo qualcosa di veloce lì.",
        "IT-A6": "Il negozio all'angolo vende frutta fresca, i giornali del giorno e ottimi biscotti fatti in casa.",
    },
}

PT = {
    "enroll": {
        "PT-R1": ("O comboio da manhã partiu com algum atraso. Pela janela viam-se campos de trigo, pequenas "
                  "aldeias e uma ou outra estrada vazia. A Marta abriu o caderno e escreveu uma lista de "
                  "coisas por fazer: ligar ao irmão, rever o orçamento e comprar pão antes de voltar a casa."),
        "PT-R2": ("Quando chegámos ao porto, o vento soprava com força e as gaivotas voavam baixo. Um pescador "
                  "explicou-nos que o mar estava demasiado agitado para sair. Tomámos um café no bar da "
                  "esquina e, ao fim da tarde, o céu limpou e finalmente pudemos subir para o barco."),
        "PT-R3": ("A biblioteca do bairro abre todos os dias das nove às oito. Tem uma sala de estudo "
                  "silenciosa, computadores para consultar o catálogo e uma secção infantil muito completa. "
                  "Aos sábados organiza oficinas de leitura e, uma vez por mês, convida um autor."),
        "PT-R4": ("Para fazer uma boa sopa de legumes é preciso paciência e lume brando. Primeiro descascam-se "
                  "as cenouras e as batatas e cortam-se em pedaços pequenos. Depois refogam-se com uma cebola. "
                  "Por fim junta-se água, sal e um fio de azeite, e deixa-se cozer uma hora."),
        "PT-R5": ("Ontem à noite houve uma trovoada impressionante. Os relâmpagos iluminavam todo o vale, e os "
                  "trovões faziam tremer os vidros. A luz foi abaixo durante quase duas horas, por isso "
                  "acendemos velas e jogámos às cartas na sala de estar. Esta manhã, as ruas estavam cheias de "
                  "ramos."),
    },
    "verify": {
        "PT-V1": ("Ao domingo, o meu avô levanta-se muito cedo para ir ao mercado. Conhece todos os vendedores "
                  "e conversa muito tempo com cada um deles. Volta sempre com fruta da época, o jornal e um "
                  "grande pão caseiro, e depois prepara o almoço para toda a família."),
        "PT-V2": ("A reunião de segunda-feira durou mais do que o previsto. Falámos do novo projeto, do "
                  "calendário e do orçamento para o próximo ano. No fim, a Laura propôs organizar uma pequena "
                  "festa para o aniversário da empresa, e toda a gente aceitou de imediato."),
        "PT-V3": ("Há alguns anos decidi aprender a tocar guitarra. No início doíam-me os dedos e os acordes "
                  "soavam muito mal, mas praticava um pouco todas as noites. Agora já consigo tocar várias "
                  "canções inteiras e, de vez em quando, até canto com os meus amigos."),
    },
    "access": {
        "PT-A1": "Antes de sair, a Lúcia fechou as janelas, desligou o rádio e deixou um bilhete na mesa da cozinha.",
        "PT-A2": "O autocarro das oito chegou atrasado, por isso fomos a pé até à praça enquanto começava a chover.",
        "PT-A3": "Todos os domingos, o padeiro do bairro faz uma tarte de maçã que esgota muito antes do almoço.",
        "PT-A4": "Durante o passeio vimos um veado, atravessámos uma ponte de madeira e almoçámos junto ao lago.",
        "PT-A5": "Se o comboio voltar a atrasar-se, apanhamos um táxi até ao hotel e jantamos qualquer coisa lá.",
        "PT-A6": "A loja da esquina vende fruta fresca, os jornais do dia e umas bolachas de chocolate caseiras.",
    },
}

CA = {
    "enroll": {
        "CA-R1": ("El tren del matí va sortir amb una mica de retard. Per la finestra es veien camps de blat, "
                  "pobles petits i alguna carretera buida. La Marta va obrir la llibreta i va escriure una "
                  "llista de coses pendents: trucar al germà, revisar el pressupost i comprar pa."),
        "CA-R2": ("Quan vam arribar al port, el vent bufava amb força i les gavines volaven baix. Un pescador "
                  "ens va explicar que el mar estava massa mogut per sortir. Vam prendre un cafè al bar de la "
                  "cantonada i, a mitja tarda, el cel es va aclarir i per fi vam pujar a la barca."),
        "CA-R3": ("La biblioteca del barri obre cada dia de nou a vuit. Té una sala d'estudi silenciosa, "
                  "ordinadors per consultar el catàleg i una secció infantil molt completa. Els dissabtes "
                  "organitza tallers de lectura i, un cop al mes, convida un autor a parlar del seu llibre."),
        "CA-R4": ("Per fer una bona sopa de verdures cal paciència i foc lent. Primer es pelen les pastanagues "
                  "i les patates, i es tallen a trossos petits. Després es sofregeixen amb una ceba. Finalment "
                  "s'hi afegeix aigua, sal i un raig d'oli, i es deixa coure tot una hora."),
        "CA-R5": ("Ahir a la nit hi va haver una tempesta impressionant. Els llamps encenien tota la vall, i "
                  "els trons feien tremolar els vidres. Es va anar el corrent durant gairebé dues hores, així "
                  "que vam encendre espelmes i vam jugar a cartes al menjador. Aquest matí, els carrers eren "
                  "plens de branques."),
    },
    "verify": {
        "CA-V1": ("Els diumenges, el meu avi es lleva molt d'hora per anar al mercat. Coneix tots els venedors "
                  "i xerra una bona estona amb cadascun. Sempre torna amb fruita de temporada, el diari i un "
                  "pa de pagès ben gros, i després prepara el dinar per a tota la família."),
        "CA-V2": ("La reunió de dilluns es va allargar més del previst. Vam parlar del projecte nou, del "
                  "calendari i del pressupost per a l'any vinent. Al final, la Laura va proposar organitzar "
                  "una petita festa per a l'aniversari de l'empresa, i tothom hi va estar d'acord."),
        "CA-V3": ("Fa uns quants anys vaig decidir aprendre a tocar la guitarra. Al principi em feien mal els "
                  "dits i els acords sonaven fatal, però practicava una mica cada nit. Ara ja sé tocar "
                  "diverses cançons senceres i, de tant en tant, fins i tot canto amb els amics."),
    },
    "access": {
        "CA-A1": "Abans de sortir, la Júlia va tancar les finestres, va apagar la ràdio i va deixar una nota.",
        "CA-A2": "L'autobús de les vuit va arribar tard, així que vam anar a peu fins a la plaça del mercat.",
        "CA-A3": "Cada diumenge, el forner del barri prepara un pastís de poma que s'acaba abans del migdia.",
        "CA-A4": "Durant l'excursió vam veure un cérvol, vam creuar un pont de fusta i vam dinar vora el llac.",
        "CA-A5": "Si el tren torna a anar amb retard, agafarem un taxi fins a l'hotel i soparem allà mateix.",
        "CA-A6": ("La botiga de la cantonada ven fruita fresca, els diaris del dia i unes galetes de xocolata "
                  "casolanes."),
    },
}

GL = {
    "enroll": {
        "GL-R1": ("O tren da mañá saíu con algo de atraso. Pola xanela víanse campos de trigo, pequenas aldeas "
                  "e algunha estrada baleira. A Marta abriu o caderno e escribiu unha lista de cousas "
                  "pendentes: chamar ao seu irmán, revisar o orzamento e mercar pan antes de volver."),
        "GL-R2": ("Cando chegamos ao porto, o vento sopraba con forza e as gaivotas voaban baixo. Un pescador "
                  "explicounos que o mar estaba demasiado axitado para saír. Decidimos tomar un café no bar da "
                  "esquina e agardar. A media tarde, por fin, o ceo despexou e puidemos subir ao barco."),
        "GL-R3": ("A biblioteca do barrio abre todos os días de nove a oito. Ten unha sala de estudo "
                  "silenciosa, ordenadores para consultar o catálogo e unha sección infantil moi completa. Os "
                  "sábados organiza obradoiros de lectura e, unha vez ao mes, convida un autor para que fale "
                  "do seu último libro."),
        "GL-R4": ("Para preparar un bo caldo fai falta paciencia e lume baixo. Primeiro pélanse as patacas e "
                  "córtanse en anacos pequenos. Despois engádense as verzas, unhas fabas e un pouco de unto. "
                  "Por último bótase auga e sal, e déixase cocer todo durante unha hora longa."),
        "GL-R5": ("Onte pola noite houbo unha treboada impresionante. Os lóstregos iluminaban todo o val, e os "
                  "tronos facían tremer os cristais. Foise a luz durante case dúas horas, así que acendemos "
                  "unhas velas e xogamos ás cartas na sala. Esta mañá, as rúas estaban cheas de pólas caídas."),
    },
    "verify": {
        "GL-V1": ("Os domingos, o meu avó érguese moi cedo para ir ao mercado. Coñece todos os vendedores e "
                  "conversa un bo anaco con cada un deles. Sempre volve con froita da tempada, o xornal e unha "
                  "boa bola de pan, e despois prepara o xantar para toda a familia."),
        "GL-V2": ("A reunión do luns durou máis do previsto. Falamos do novo proxecto, do calendario e do "
                  "orzamento para o ano que vén. Ao final, a Laura propuxo organizar unha pequena festa para o "
                  "aniversario da empresa, e todo o mundo estivo de acordo axiña."),
        "GL-V3": ("Hai uns anos decidín aprender a tocar a guitarra. Ao principio doíanme os dedos e os "
                  "acordes soaban fatal, pero practicaba un pouco todas as noites. Agora xa sei tocar varias "
                  "cancións enteiras e, de cando en vez, ata canto cos meus amigos."),
    },
    "access": {
        "GL-A1": "Antes de saír, a Lucía pechou as fiestras, apagou a radio e deixou unha nota na mesa da cociña.",
        "GL-A2": "O autobús das oito chegou tarde, así que fomos camiñando ata a praza mentres empezaba a chover.",
        "GL-A3": "Cada domingo, o panadeiro do barrio prepara unha torta de mazá que se esgota antes do mediodía.",
        "GL-A4": "Durante a excursión vimos un cervo, cruzamos unha ponte de madeira e xantamos na fervenza.",
        "GL-A5": ("Se o tren volve atrasarse, colleremos un taxi ata o hotel e ceamos algo rápido alí mesmo, "
                  "sen présa."),
        "GL-A6": "A tenda da esquina vende froita fresca, os xornais do día e unhas galletas de chocolate caseiras.",
    },
}

EU = {
    "enroll": {
        "EU-R1": ("Goizeko trena berandu samar irten zen. Leihotik gari-soroak, herri txikiak eta errepide "
                  "hutsen bat ikusten ziren. Martak bere koadernoa ireki eta egiteko gauzen zerrenda bat "
                  "idatzi zuen: anaiari deitu, aurrekontua berrikusi eta etxera itzuli aurretik ogia erosi."),
        "EU-R2": ("Portura iritsi ginenean, haizeak indar handiz jotzen zuen eta kaioak behetik zebiltzan. "
                  "Arrantzale batek esan zigun itsasoa harrotuegi zegoela ateratzeko. Izkinako tabernan kafe "
                  "bat hartu genuen. Arratsaldean, azkenean, zerua oskarbitu zen eta itsasontzira igo ginen."),
        "EU-R3": ("Auzoko liburutegia egunero irekitzen da, bederatzietatik zortzietara. Ikasketa-gela isil "
                  "bat du, katalogoa kontsultatzeko ordenagailuak eta haurrentzako atal oso osatua. "
                  "Larunbatetan irakurketa-tailerrak antolatzen ditu, eta hilean behin idazle bat dator."),
        "EU-R4": ("Barazki-zopa on bat prestatzeko, pazientzia eta su motela behar dira. Lehenik, azenarioak "
                  "eta patatak zuritu eta zati txikitan mozten dira. Ondoren, tipula batekin frijitzen dira. "
                  "Azkenik, ura, gatza eta olio pixka bat gehitzen dira, eta ordubetez egosten da."),
        "EU-R5": ("Atzo gauean ekaitz ikaragarria izan zen. Tximistek haran osoa argitzen zuten, eta trumoiek "
                  "leihoetako kristalak dardarka jartzen zituzten. Argia ia bi orduz joan zen; beraz, kandela "
                  "batzuk piztu eta kartetan aritu ginen egongelan. Gaur goizean, kaleak adarrez beteta "
                  "zeuden."),
    },
    "verify": {
        "EU-V1": ("Igandeetan, nire aitona oso goiz jaikitzen da azokara joateko. Saltzaile guztiak ezagutzen "
                  "ditu eta denbora luzez aritzen da bakoitzarekin hizketan. Beti itzultzen da sasoiko "
                  "fruitarekin, egunkariarekin eta ogi handi batekin, eta gero bazkaria prestatzen du."),
        "EU-V2": ("Asteleheneko bilera aurreikusitakoa baino luzeagoa izan zen. Proiektu berriaz, egutegiaz "
                  "eta datorren urteko aurrekontuaz hitz egin genuen. Amaieran, Laurak enpresaren urteurrena "
                  "ospatzeko jai txiki bat proposatu zuen, eta denok berehala onartu genuen."),
        "EU-V3": ("Duela urte batzuk gitarra jotzen ikastea erabaki nuen. Hasieran behatzetan mina nuen eta "
                  "akordeak oso gaizki entzuten ziren, baina gauero apur bat praktikatzen nuen. Orain hainbat "
                  "abesti jo ditzaket eta, noizean behin, lagunekin abestu ere egiten dut."),
    },
    "access": {
        "EU-A1": "Irten aurretik, Luziak leihoak itxi zituen, irratia itzali zuen eta ohar bat utzi zuen mahaian.",
        "EU-A2": "Zortzietako autobusa berandu iritsi zen; beraz, oinez joan ginen plazaraino euria hasi zenean.",
        "EU-A3": "Igandero, auzoko okinak sagar-tarta bat egiten du, eta eguerdia baino askoz lehenago agortzen da.",
        "EU-A4": "Txangoan orein bat ikusi genuen, egurrezko zubi bat zeharkatu eta ur-jauzian bazkaldu genuen.",
        "EU-A5": "Trena berriro berandu badator, taxi bat hartuko dugu hotelera eta han zerbait afalduko dugu.",
        "EU-A6": "Izkinako dendak fruta freskoa, eguneko egunkariak eta etxeko txokolatezko gailetak saltzen ditu.",
    },
}

POOLS = {"ca": CA, "gl": GL, "eu": EU, "fr": FR, "pt": PT, "de": DE, "it": IT}
