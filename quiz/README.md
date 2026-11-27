# Квіз «Вусы Скарыны»

FastAPI + SQLite, без Docker. Банк пытанняў — `../data/question_bank.json` (будуецца `scripts/build_bank.py`).

## Усталёўка на Oracle (як астатнія сайты: служба + nginx)
```
cd ~/vusy-skaryny/quiz
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py adduser ІМЯ --admin        # агульны лагін для групы
sudo cp deploy/vusy-quiz.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now vusy-quiz
sudo cp deploy/nginx-quiz.conf /etc/nginx/sites-available/vusy-quiz && sudo ln -s /etc/nginx/sites-available/vusy-quiz /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d quiz.138-2-152-69.sslip.io
```
Абнаўленне: `git pull && sudo systemctl restart vusy-quiz`.

База і сакрэт — `quiz/config/` (не ў git). Шлях/порт/імя карыстальніка ў `deploy/vusy-quiz.service` праверыць пад сервер.
