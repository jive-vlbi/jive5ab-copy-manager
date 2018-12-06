<h1>Jive5ab Copy Manager</h1>

<p>
Jive5ab Copy Manager is a GUI extracted from a larger software package used at JIVE to manage FlexBuff recordings.
Part of the software, gives an 'explorer like' tree view of FlexBuff recordings in an (experiment, station, scan) hierarchy.
It includes a wrapper around m5copy.

<h2>Installation</h2>
<ul>
<li>The software requirements are python 2.7 and the PyQt4 (Debian package python-qt4).  
<li>Download the latest version: <a href="https://github.com/jive-vlbi/jive5ab-copy-manager/archive/master.zip">jive5ab_copy_manager-master.zip</a>.
<li>Extract the contents of the file, the executable is jcm.py
</ul>

<h2>Quick tutorial</h2>
The start screen will show you 2 of the same widgets side by side, to compare and copy.
The first thing to do is select the machine type you want to browse and then select the host.
A few hosts per type are predefined in the config.json file, a few hosts from here at JIVE serve as an example. You probably want to edit this file, or you can just type the host directly into the host selection box.
The syntax for the direct option is [&lt;user&gt;@]&lt;host name/IP&gt;[:&lt;control port&gt;[:&lt;data IP&gt;]].

<p>
With the host selected, the program will go look for recordings on the the machine.
In file and FlexBuff view, this is done using SSH.
This is where the &lt;user&gt; comes into play: a requirement is that an SSH key is installed that allows password-less access to the machine.
Without a user, the user running the program is used on the target machine.

<p>
Having found the recordings, the program will present a tree view, in which you can make a selection with the left mouse button.
The right mouse button will present an action menu to act on the selection.
The program is very particular about the selection, to make sure that the intent of the action is clear.
The error message should help determine what the program thinks is still unclear.

<p>
One action is a wrapper around m5copy. This will pop up a new window in which you can set a few options, remember to click apply after changing these options. This will change the text in the bottom of the view. Clicking go will execute the text line by line (you can also directly edit the text).

<p>
For questions/comments, please contact me <a href="mailto:eldering@jive.eu">(Bob Eldering)</a>
