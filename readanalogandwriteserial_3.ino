
//Reads 3 analog voltages and writes them to the serial port as fast as possible.
//Note that there is no conditioning of the values to speed up the process, hence 0-5V reads as 0-1023 integer
const int analogInPinx = A3;   
const int analogInPiny = A4; 
const int analogInPinz = A5; 

int x = 0;    
int y = 0;    
int z = 0;       

void setup() {
  // initialize serial communications. Tested on an Arduino UNo and 1m USB cable up to 2M bauds:
  Serial.begin(115200);
}

void loop() {
  /We alternate the analog reads and the serial prints to let the analog to digital converter time to update.
    x = analogRead(analogInPinx);
  Serial.print(x);
  Serial.print(","); 
  y = analogRead(analogInPiny);
  Serial.print(y);
  Serial.print(",");   
  z = analogRead(analogInPinz);
  Serial.println(z); // Newline at the end
}