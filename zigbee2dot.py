import sqlite3
conn = sqlite3.connect('zigbee.db')
c = conn.cursor()


header="""
digraph finite_state_machine {
	rankdir=TB; 
        labeldistance=10;
        packMode="node";
	node [shape = doublecircle]; "0";
	node [shape = circle];"""
print(header)
for row in c.execute("SELECT * from topology"):
    if row[2]:  
        print("\u0022{}\u0022 -> \u0022{}\u0022 [ label = \u0022{}/{}\u0022 ]; ".format( row[0],row[1],row[2],row[4]))
print("}")
