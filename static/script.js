
function buttonFirePressed(){
    var xhttp = new XMLHttpRequest();
    xhttp.open("GET", "/fire?fire_value=True", true);
    xhttp.send();
}

function buttonNotFirePressed(){
    var xhttp = new XMLHttpRequest();
    xhttp.open("GET", "/fire?fire_value=False", true);
    xhttp.send();
}

function start(){
    var xhttp = new XMLHttpRequest();
    xhttp.open("GET", "/start", true);
    xhttp.send();
}

function stop(){
    var xhttp = new XMLHttpRequest();
    xhttp.open("GET", "/stop", true);
    xhttp.send();
}

function getDb(){
    var xhttp = new XMLHttpRequest();
    xhttp.onreadystatechange = function() {
        if (this.readyState == 4 && this.status == 200) {
            console.log(this.responseText)
            var db = JSON.parse(this.responseText);
            if (db['found_someone'] == true){
                if (db['fraction'] == 1){
                    document.getElementById("person").style.color="green";
                    document.getElementById("person").innerHTML='Обнаружен "свой"';
                } else if (db['fraction'] == -1){
                    document.getElementById("person").style.color="red";
                    document.getElementById("person").innerHTML= 'Обнаружен "чужой"';
                } else if (db['fraction'] == 0){
                    document.getElementById("person").style.color="grey";
                    document.getElementById("person").innerHTML= 'Обнаружен неизвестный';
                }
                document.getElementById("person").style.visibility="visible";
                document.getElementById("alarm-block").style.visibility="visible";
            } else{
                document.getElementById("person").style.visibility="hidden";
                document.getElementById("alarm-block").style.visibility="hidden";
            }
        }
    };
    xhttp.open("GET", "/get_db", true);
    xhttp.send();

}
