## Google Nerfed - A play on words because Google is always broken (nerfed) and when I started this project it was Google Earth that didn't work, so decided to write my own map platform. 

The test environment (this machine) is running Windows, without Docker. The development server is Ubuntu and we deploy via Docker compose. The production server is also Ubuntu and we deploy with docker compose ther too. 

The conda environment is map, please use it whenever you use the terminal.

For the telegram related task, there are some reference files in "telegramold" these are from an unfinished piece of work which leveraged Telethon to identify posts and had formal API Keys & Auth set up for Telegram. The telegram "mapping_usebot.session" file should work to authenticate. Ensure this is added to .gitignore before pushing any changea. 

The issue:
- Our Russian radar "air alerts" pulled Telegram alert messages from the "radarrussia" Telegram channel. This uses our original telegram implementation also known as scraping Telegram every 60 seconds. It will works reliably.
- The telegram data (e.g. determining the threat, the geolocation, and filtering the messages to remove adverts/spam) takes place in main.py 
- The Telegram channel radarrussia has stopped posting the vast majority of it's air alerts, apart from a minority. Instead individual telegram radar channels, one for each Oblast or major town receive the air alerts related to "drone detection" or "airdefence". Considering how many new chanels there are, it isn't feasible to poll them all instead. 
- A previous effort to connect telegram to multiple channels and only post selective posts using a redex / config file was largely finished in another branch but never merged. In addition to the "telegramold" python files. THe docker compose file had an additional service for the telethon worker to run. 
- Please can you implement all of the functionality to captuer all aleerts from each of the grounds using the principles I had set up before. However it's important that the message parsing rules, the geolocation rules (and overrides) and config from the old telegram polling method continues to work, and the other groups can slot into this workflow.
- the channel zn.ua often published video or images of Ukrainian long range strikes which often ha da consistent emoji pattern to match the posts. (see telegram_config.py) - I would like to be able to implement this funcitonality so that 1) telegram post matches a regex 2) The telegram post has Russian location identified and 3) A pin is added to the map probably on the "live russian radar" layer for "hits". Since that implementation we've added functionality to customise map markers per marker, per custom field (e.g. category) or per layer.  And custom fields can now be added such as source links, whereas the original plan for the map had been to embed the source telegram post. Instead of embedding we should add the telegram post text and photos to the "location intelligence" popup and link to the post instead. Additionaly there needs to be a way to edit telegram post automated map markers via the /admin pages. The radar Russia functionality already has working admin tools which work as is (e.g for overrides). 
- The list of telegram groups are helow, the priority is to restore the air alert functionality as is. The data is only published on the map for 24 hours by design, however it would be really useful to keep a complete history of evert alert for longitudinal data (in a database, rahter than a change to the map). E.g. the location info, the threat type, the nominatim query, timestamp etc. And I'd like to be able to populate this from the historical telegram messages for the analytics. 

I have subscribed to all telegram groups, they are: 


☄️Липецк и область - https://t.me/radar_lipetskk 

☄️Орел и область - https://t.me/radar_oreI 

☄️Воронеж и область - https://t.me/radar_voronezh 

☄️Смоленск и область - https://t.me/radar_smolensk 

☄️Москва и область - https://t.me/radar_moscoww 

☄️ Тверь и область - https://t.me/radar_tver

☄️Тула и область - https://t.me/radar_tuIa 

☄️Волгоград и область - https://t.me/radar_volgograd 

☄️Тамбов и область - https://t.me/radar_tambov 

☄️Ростов (Таганрог) - https://t.me/radar_rostovv 

☄️Морозовск - https://t.me/radar_rostovv 

☄️Краснодарский край (Ейск) - https://t.me/radar_kras 

☄️Новороссийск - https://t.me/radar_kras 

☄️Крым - https://t.me/radar_crimeaa 

☄️Брянск - https://t.me/radar_bryanskk 

☄️Белгород - https://t.me/radar_beIgorod 

☄️Курск - https://t.me/radar_kurskk

☄️ Саратов и область - https://t.me/rada_saratov

☄️ Энгельс и область - https://t.me/radar_engels

 ☄️ Елец - https://t.me/radar_elets

☄️ Рязань и область - https://t.me/radar_ryazan

☄️Калуга и область - https://t.me/radar_kaluga

☄️ Владимир - https://t.me/radar_vladimir

☄️ Ливны - https://t.me/radar_livni

☄️ Республика Татарстан (Казань) - https://t.me/radar_tatarstann

☄️ Кубань - https://t.me/Kubanoperativ

☄️ Приморско-Ахтарск - https://t.me/radar_ahtari

☄️ Самара и область - https://t.me/radar_samaraa

☄️ Республика Башкортостан - https://t.me/radar_bashkortostan

☄️ Нижегородская область - https://t.me/radar_nizhniinovgorod

☄️ Вологда и область - https://t.me/radar_vologda

☄️ Республика Удмуртия (Ижевск) - https://t.me/radar_udmurtiya

☄️ Питер и область - https://t.me/radar_peterburg

☄️ Астрахань и область - https://t.me/radar_astrakhann

☄️ Ульяновск и область - https://t.me/radar_ulyanovsk

☄️ Республика Мордовия - https://t.me/radar_mordoviya

☄️ Республика Чувашия - https://t.me/radar_chuvashiya

☄️ Ставропольский край - https://t.me/stavropol_radar

☄️ Республика Адыгея - https://t.me/radar_adygeya

☄️ Пензенская область - https://t.me/radar_penzaa

☄️ Сочи(Адлер, Лазаревское, Сириус) - https://t.me/radar_sochiii

☄️ Псковская область - https://t.me/radar_pskovv