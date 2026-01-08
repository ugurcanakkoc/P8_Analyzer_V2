# KI Strategie UVP Schaltschränke | Regelmeeting

**Meeting Date:** 10th Dec, 2025 - 3:30 PM

---

**Maximilian König** *[02:42]*: Hello. 
**Mustafa Vural** *[03:13]*: Hallo. 
**Maximilian König** *[03:14]*: Übrigens, wir haben nur als Gedanke zum Thema, dass du immer als Mustafa drin bist. Das ist eine super große Herausforderung, weil das bei ganz vielen Menschen so ist, dass die nicht unbedingt immer den richtigen Account verwenden. Wenn du dann versuchst automatisiert solche Gesprächsmitschnitte. 
**Maximilian König** *[03:31]*: Auszuwerten, kommt da nur Müll bei raus. 
**Maximilian König** *[03:34]*: Weil wenn ich dann fragen würde, wir haben aktuell nichts laufen, das tut. Aber wenn ich jetzt fragen würde, was hat Hasan im letzten Meeting zu dem und dem gesagt würde hä, Hasan war gar nicht dabei. Ist spannend. 
**Mustafa Vural** *[03:48]*: OK, da muss ich mal aufpassen. 
**Maximilian König** *[03:53]*: Ja, aktuell werten wir das nicht automatisiert aus. Wir haben das schon mal versucht, aber unter anderem wegen solchen Problemen ist es Teil nicht schön. Gut. Vielen Dank für die Spezifikation, was als nächstes zu tun ist. Wir sind dran. Wir haben auch gesehen, du hast ein paar Trainingsbilder eingefügt. Das erste, was wir machen, ist mehr Trainingsdaten erzeugen auf Basis eben der Vektorgrafiken, also alle Vektorgrafiken durchnudeln und in Trainingsbilder umwandeln, das Yodo Modell weiter zu optimieren. Kannst du uns mal noch den Zugriff auf die anderen Schaltplan PDFs geben, die ihr so verwendet? Da liegt ja gerade nur eine im Repository. Ihr hattet uns auch schon mal andere geschickt in der Vergangenheit, aber ich bin mir relativ sicher, du hast einen Ort, wo die liegen. 
**Maximilian König** *[04:48]*: Wenn du mir das noch mal geben kannst, wäre super. 
**Maximilian König** *[05:14]*: Am liebsten wäre mir, wenn du mir nicht einzelne schickst, sondern mir einen Zugriff auf euren Speicherort gibst, wo die alle liegen. 
**Maximilian König** *[05:21]*: Wenn das geht. Das ist schwierig. Ist schwierig. Okay. 
**Mustafa Vural** *[05:26]*: Außerdem muss man den kompletten Server öffnen, weil der ist immer projektbezogen. 
**Maximilian König** *[05:32]*: Okay, okay. Das Ding ist halt, wenn Uhr immer selbst aussucht, besteht halt die Gefahr, dass ich einfach nicht genug sehe. Die Herausforderung ist so ein bisschen, ich will vermeiden, dass das Modell, das wir trainieren, Overfitting betrachtet. Dafür ist es halt gut, eine zufällige Auswahl machen zu können. 
**Mustafa Vural** *[05:49]*: Deswegen habe ich ihm gerade eben gesagt, er soll von unterschiedlichen Kunden quasi Scharfähne schicken. 
**Maximilian König** *[05:53]*: Okay, okay, gut. Ja, das hilft auch. Wenn die händische Auswahl breit genug ist, geht es auch Klar. Wenn ihr das nicht teilen könnt, ist okay, dann hätte ja sein können. 
**Maximilian König** *[06:04]*: Aber gut, wenn ihr das getrennt habt, ne? 
**Maximilian König** *[06:07]*: Ansonsten ist klar, was du von uns haben möchtest, kriegen wir hin. Genau. 
**Mustafa Vural** *[06:15]*: Weiß nicht, ob der UR das schon gesagt hat. Er ist diese Woche quasi für. 
**Maximilian König** *[06:19]*: Hat er uns geschrieben. Ja, ja, deswegen hatte er geschrieben. Deswegen habe ich da jetzt nicht weiter nachgefragt und dachte mir, wir sehen uns jetzt da kann ich jetzt fragen, aber es ist klar. 
**Maximilian König** *[06:28]*: Ist aber okay, dann machen wir das. 
**Maximilian König** *[06:31]*: Für dich und trainieren das Modell und. 
**Maximilian König** *[06:34]*: Gucken, was dann für eine Qualität rauskommt. 
**Mustafa Vural** *[06:53]*: Okay, ich versuche die Frage mal ein bisschen verständlicher. Rüberzubringen und zwar zwischen Schaltplanerstellung und Schaltplanerstellung gibt es auch Unterschiede. Also einer macht im E Plan, der andere WS CAD und der andere macht es irgendwo komplett anders. Und ein Schütz zum Beispiel, der sieht bei dem einen anders aus als bei dem anderen. Deswegen frägt er jetzt, sollen wir für alle Kunden ein Modell trainieren oder sollen wir jeweils für einen Kunden oder sag mal für eine. Variante. Eine Software trainieren? 
**Maximilian König** *[07:34]*: Das ist eine super, super Frage. Wisst ihr a priori, mit welcher Software der Plan erstellt wurde? 
**Mustafa Vural** *[07:46]*: Wir können es vermuten oder wir können es eventuell auch wissen. 
**Maximilian König** *[07:51]*: Ich weiß es natürlich nicht. Ich müsste mir das jetzt einfach auch mal ansehen. Also was ist der Standardansatz? Der Standardansatz ist so zu tun, als gäbe es diese Unterschiede nicht. Ein Modell zu trainieren, sich die Performance des Modells anzusehen, in der Performance dann zu schauen, ist die Performance auf den unterschiedlichen Kategorien besser oder schlechter, als wenn ich es einzeln trainiere und dann die Entscheidung zu treffen. Weil ich weiß nicht a priori, ob die Unterschiede, die in den Daten drin sind, das Modell besser oder schlechter machen. Es kann sein, dass das Modell gut in der Lage ist, die unterliegende Struktur zu abstrahieren und quasi das Konzept eines Schütz visuell zu verstehen, sodass es über alle Anbieter hinweg gut funktioniert. Genauso kann es sein, dass die visuellen Darstellungen zu sehr divergieren und er das nicht gut verallgemeinern kann. Das weiß ich aber ohne mir die Daten. 
**Maximilian König** *[08:53]*: Also das weiß ich a priori schlichtweg nicht. Deswegen ist so ein Modelltraining ist eigentlich immer iterativ. Ich probiere das einfach aus, du baust dir deine Pipeline, du probierst es aus und dann wertest du aus und dann. 
**Maximilian König** *[09:06]*: Siehst du, was passiert. 
**Maximilian König** *[09:08]*: Es ist natürlich viel schöner, wenn wir ein Modell verwenden können. Das ist viel weniger aufwendig und dann kann ich mir diesen Schritt herauszufinden, von wem das ist, halt sparen. Ich kann aber auch nicht ausschließen, dass ich einzelne Modelle brauche. Ich würde aber erstmal ein Modell machen wollen. Aber das ist genau der Grund, warum ich sage, ich hätte gerne mal mehr gesehen, damit man genau zu diesen Fragen kommt. Eine Idee noch, also so eine kleine Inspiration. Die Large Language Models, die wir so viel verwenden, die sind ja gerade deswegen stark, weil sie abstrahieren und allgemein sind. Also früher hat man viel spezifischere Modelle trainiert, aber jetzt aktuell geht der Trend ja zu großen Modellen, die dann trotzdem stark sind. Deswegen ist inhaltlich der Ansatz zu versuchen, große Modelle, die viel können, zu trainieren, erstmal nicht absurd. 
**Maximilian König** *[10:52]*: Wie gesagt, wenn das nicht funktioniert, muss man kleinere Modelle machen, aber erstmal versucht. 
**Maximilian König** *[10:56]*: Man, große Modelle zu machen. 
**Maximilian König** *[11:01]*: Okay. Also bestes Beispiel, ChatGPT spricht ja auch Türkisch. Das müsste es nicht können. Man hätte ChatGPT auch trainieren können. Dass es nur Englisch spricht, hat man halt bewusst nicht gemacht, sondern man hat ihm halt klar vor allem Englisch gezeigt, aber eben auch andere Sprachen und es funktioniert gut. 
**Mustafa Vural** *[11:38]*: Aber ihr werdet jetzt quasi gucken, dass ihr, wenn der U die Sachen zur Verfügung stellt, dass ihr bis nächste Woche mal was präsentieren könnt oder dass ihr sagt, okay, hier, wir haben. 
**Maximilian König** *[11:47]*: Dass wir das mal trainieren. Genau. 
**Maximilian König** *[11:49]*: Okay. 
**Maximilian König** *[11:51]*: Ja, aber ich muss nächste Woche eine Vertretung reinschicken, weil ich tatsächlich schon im. 
**Maximilian König** *[11:56]*: Urlaub bin, Aber das kriegen wir hin. Okay. 
**Mustafa Vural** *[12:02]*: Dann habe ich noch Idris Halbe eine Frage. Einmal wird es vermutlich noch nicht wissen, schätze ich, aber vielleicht weiß er es ja auch schon. Letztens habe ich eine Werbung von Christoph gesehen. Die Werbung ging aber nicht über neurawork, es ging über irgendwas anderes. Ja. Gibt da mehrere Firmen quasi, wo ihr tätig seid? 
**Maximilian König** *[12:26]*: Es gibt eine. Es gibt eine andere Firma, die heißt Evan. 
**Mustafa Vural** *[12:31]*: Grünes Logo. 
**Maximilian König** *[12:34]*: Ich kenne das Logo nicht auswendig, muss ich ehrlich zugeben. Warte mal, ich kriege das. Ja hier. Warte, du meinst. Du meinst das hier? 
**Maximilian König** *[12:51]*: Ja, es kann sein. Kann sein, ja. 
**Maximilian König** *[12:55]*: So. Das ist ein Nebenprojekt, was einfach eine Plattform ist, wo man niedrigschwellig GPTs ausrollen kann. 
**Mustafa Vural** *[13:09]*: Was heißt das genau? 
**Maximilian König** *[13:12]*: Du kennst das, Wenn du bei ChatGPT dir ein neues GPT erstellst, dann gibst du ja einen Prompt ein und dann macht er irgendwas auf der Basis. Dieses F ist quasi eine Plattform, für Leute, die wirklich ganz wenig Ahnung von KI haben, so einen Prompt einzustellen und dann in diesem Prompt Variablen zu definieren, das an Enduser auszurollen, die dann nur noch diese Variablen befüllen müssen. Also so klassisches Beispiel. Du willst irgendwie einen Sales Pitch machen, du schreibst dann einen Prompt rein und in dem Prompt gibt es dann nur das Feld, was ist die Branche, wie heißt die Person und wie groß ist deren Firma oder so. Und dann wird auf Basis dieser wenigen Eingabewerte dieser Pitch dann geschrieben mit Large. 
**Maximilian König** *[14:02]*: Language Model und du kriegst ihn dann zurück. 
**Maximilian König** *[14:04]*: Das ist das, was diese Plattform macht. Und das ist entstanden aus einer Zusammenarbeit mit einer Marketingfirma, die wir beraten haben und ist halt wirklich in diesem Marketingbereich. Ist das jetzt erfolgreich interessant, dass du die Werbung dafür bekommen hast, weil eigentlich. 
**Maximilian König** *[14:20]*: Bist du wirklich nicht die Zielgruppe dafür. 
**Maximilian König** *[14:23]*: Aber gut, man weiß halt immer nicht. 
**Maximilian König** *[14:24]*: Wie das funktioniert, ne? 
**Maximilian König** *[14:25]*: Und da haben wir jetzt einen Kollegen bei uns, der das auch quasi vermarktet, aber ich habe damit ehrlich gesagt wenig zu tun und ist jetzt glaube ich, für euch nicht so wahnsinnig interessant. Ihr seid auf einem anderen Niveau unterwegs. 
**Maximilian König** *[14:38]*: Okay, verstanden. 
**Mustafa Vural** *[14:39]*: Dann brauchen wir uns nicht weiter zu verfolgen. Ich habe einfach die Werbung gesehen und dann habe ich gesagt, ich frage einfach nach. 
**Maximilian König** *[14:44]*: Nee, nee, verstehe ich. Also, aber ja, hätten wir, hätten wir mit euch darüber gesprochen, wenn es für euch interessant gewesen wäre. Aber es ist wirklich vor allem für, siehst ja auch an der Aufmachung, das ist wirklich für Berater, für Marketer, für Leute, die weiter weg von der Technik. 
**Maximilian König** *[14:58]*: Sind als ihr, also für Leute, die. 
**Maximilian König** *[15:01]*: Vor allem auch nicht selber programmieren können, die das brauchen. Wer selber programmieren kann, braucht das so auch nicht. 
**Mustafa Vural** *[15:11]*: Wann seid ihr wieder zurück aus dem. 
**Maximilian König** *[15:12]*: Urlaub nach Weihnachten, ehrlich gesagt. Also wir lesen alle unsere Mails und so, aber wir machen quasi zwischen 24 und, keine Ahnung, Neujahr machen wir die Firma sogar ganz offiziell zu. 
**Maximilian König** *[15:24]*: Da ist Firmenurlaub. 
**Maximilian König** *[15:27]*: Also Das heißt am 25 gut, da gibt es offensichtlich keinen Call und am ersten halt auch nicht. Also wir sind quasi genau die zwei. 
**Mustafa Vural** *[15:37]*: Wochen vom. 
**Maximilian König** *[15:41]*: Wir sind dann Freitag quasi wieder da, glaube ich. Warte, ich gucke noch mal nach, wann. 
**Maximilian König** *[15:43]*: Wir Firmenurlaub haben, aber wir sind dann. 
**Maximilian König** *[15:46]*: Zwei Wochen im Jahreswechsel ist die Firma wirklich zu für Nächste Woche kümmere ich mich, dass ihr eine Vertretung reinbekommt, die das Ergebnis vorstellen kann. Da sind noch welche da bin ich schon weg, aber es sind noch Kollegen anwesend. Genau, und dann sind wir im Januar wieder da. Und dann im Januar ist ja der Plan entsprechend das Projekt noch zum Erfolg zu führen. Wir müssen da jetzt auch nicht so super exakt sein. Theoretisch läuft im Januar unser Vertrag aus. Wir wollen es ja noch fertig kriegen. Also ist jetzt nicht so. Wir müssen dann, wir werden jetzt nicht sagen Stichtag und danach sperren wir die Kanäle. 
**Maximilian König** *[16:22]*: Also das haben wir jetzt nicht vorzutun. 
**Maximilian König** *[16:25]*: Wäre ein bisschen unhöflich wahrscheinlich. Ich gucke gerade mal, wann der Firm, aber geh mal davon aus, dass die zwei Wochen im Jahreswechsel wir halt alle nicht da sind. Ich weiß nicht, wie ihr das macht, aber wahrscheinlich ist es in der Türkei nicht so. 
**Mustafa Vural** *[16:35]*: Wir müssen weiterarbeiten. Wir haben großen Auftrag, deswegen muss jeder arbeiten. 
**Maximilian König** *[16:40]*: Echt jeder. 
**Mustafa Vural** *[16:43]*: Die nicht rechtzeitig ihren Urlaub gestellt haben. 
**Maximilian König** *[16:48]*: Wir probieren das aus, dass wir tatsächlich die Firma zu machen. Wir haben Pflichturlaub tatsächlich. 
**Mustafa Vural** *[16:53]*: Gut, dann vielen Dank. Und nächste Woche sind wir gespannt, was dabei rauskommt jetzt. 
**Maximilian König** *[16:59]*: Ja, ich bin auch gespannt, was dabei rauskommt. Ich weiß es ja auch noch nicht. Das ist immer das Witzige. Also auch als jemand, der das theoretisch weiß, weiß du nicht, ob das Modell funktioniert oder nicht. 
**Mustafa Vural** *[17:10]*: Gut, vielen Dank. Schönen Abend noch. 
**Maximilian König** *[17:13]*: Schönen Abend euch. 
**Mustafa Vural** *[17:13]*: Tschüss. 
