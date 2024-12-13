![Animation](https://github.com/user-attachments/assets/fd9993d5-7ce8-4022-b4be-dc1fbd60ebca)


Having recently purchased a Bambu A1 mini, I found myself to be quite impressed with the quality and strength of the prints produced, but was soon limited to the scale of what I can create given the small printing size. To challenge this, I decided to create an add-in within [Autodesk Fusion](https://www.autodesk.com/products/fusion-360/overview) that would allow me to create larger scale projects using readily available wooden dowels commonly found at any hardware store.

My goal with this project is to create funtional and afforable furniture for my somewhat barren apartment. Having looked online for existing projects, my search came up empty for any viable tools especially ones design for Fusion which I am already comfortable with. However, I did find [this YouTube video](https://www.youtube.com/watch?v=CltgaYb8Gkw) which spark inspiration for the joint itself. 

Starting development for Fusion was straightforward as Fusion provides boilerplate examples that I was able to remix for my functionality. All scripting done for the add-in is done in either C++ or Python and I had decided to go with the latter as the Autodesk [API documentation](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-A92A4B10-3781-4925-94C6-47DA85A4F65A) was much more substantial.    

Developing code for a 3D environment requires lots of object parameters which led me down the deep, yet robust, object model within Fusion. My plan going into this was as follows: 
1. Check for and find the intersecting point of the cylinder faces.
2. Draw a line from the center of each face to the intersection point.
3. Create two [sketches](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-3D-SKETCH) on each selected face (one for the drilled in dowel thread cap, the other for the joint piece).
4. [Sweep](https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-SWEEP-SOLID) the sketch profiles along the intersection lines.  
5. Add outer threading to the cap and inner threading to the joint.

Going forward with this project, I plan on adding filets the edges to round out the design, creating a solid sphere the intersection point, and developing a web application to recreate the modeling and tool process to avoid the Fusion entry barrier for new designers (currently in development!). 

To use this in you Fusion projects, upzip the project in your %appdata%\Autodesk\Autodesk Fusion\API\AddIns directory and add it through the UTILITIES tab.
