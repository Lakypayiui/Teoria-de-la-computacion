# Teoria-de-la-computacion
Programa 1TC Comandos
Instalar brew 
con brew instalar Nanogui
cd /Users/ian/Desktop/Escom/Teoria/Programa1/
clang++ -std=c++17 -I./nanogui/include -I./nanogui/ext/eigen -I./nanogui/ext/nanovg/src -I/opt/homebrew/include -L./nanogui/build -L/opt/homebrew/lib -lnanogui -lglfw -lpthread -framework Cocoa -framework Metal -framework QuartzCore -o ProgramaUI nanogui/Programa1.cpp

clang++ -std=c++17 -Wno-deprecated-declarations -I./nanogui/include -I./nanogui/ext/eigen -I./nanogui/ext/nanovg/src -I/opt/homebrew/include -L./nanogui/build -L/opt/homebrew/lib -lnanogui -lglfw -lpthread -framework Cocoa -framework Metal -framework QuartzCore -framework AppKit -o ProgramaUI nanogui/Programa1_4.mm

g++ -std=c++11 -pthread -lpthread -o graficar nanogui/Grafica1.cpp
./graficar


./ProgramaUI

export DYLD_LIBRARY_PATH=/Users/ian/Desktop/Escom/Teoria/Programa1/nanogui/build:$DYLD_LIBRARY_PATH
./ProgramaUI

gnuplot graficar.gnuplot 

Para n=2
Epsilon
0
1
00
01
10
11
No linea. Ceros, unos, logeceros, logeunos

#####################################
Programa2

Tablero: 
q0 q1 q2 q3
q4 q5 q6 q7
q8 q9 q10 q11
q12  q13 q14 q15

Con n=3 

 agente1 iniciando en q0 
Archivo 1
 q0 -> q5 -> q10 -> q15
 archivo 2
 q2-> q6 -> q10 -> q14
