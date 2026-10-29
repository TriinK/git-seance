# Terminal demo for the DEV post. Render with:  vhs docs/demo.tape
# Needs: brew install vhs   (pulls in ttyd + ffmpeg)
#        ~/Downloads/angular.js = a full clone of https://github.com/angular/angular.js
#        Ollama running with gemma4:e4b pulled

Output docs/demo.gif

Set FontSize 15
Set Width 1300
Set Height 760
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set PlaybackSpeed 1.5

Type "cd ~/Downloads/angular.js"
Enter
Sleep 1s

Type "seance haunt --limit 3"
Enter
Wait+Screen@180s /Advice from beyond/
Sleep 5s

Type "clear"
Enter
Type "seance why src/ng/httpBackend.js:59"
Enter
Wait+Screen@180s /Every commit the ghost cited is real/
Sleep 6s
