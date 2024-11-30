### Custom user commands usage
In some cases you need to make some specific actions on page after challenge solving (click, fill form, ...).
For this case you can implement own command over extension.

uncomment in docker-compose.yml next lines :
```
    volumes:
      - ./examples/custom_user_commands/:/opt/flare_bypasser/extensions/
```
Now you can pass your extension (python module) to examples/custom_user_commands/ folder,
this folder already contains implementation of **my-click** in CustomUserCommands.py
my-click command can be called with next command (up docker before):
```
curl -XPOST 'http://localhost:20080/command/my-click' \
  -H 'Content-Type: application/json' \
  --data-raw '{"maxTimeout": 60000, "url": "https://torrentleech.pl/login.php?returnto=%2F"}'
```

You can use CustomUserCommands.py as base for implement your command.
Copy it into some py file inside examples/custom_user_commands/ (docker load all py files from this folder).
Change in get_user_commands **my-click** to your command name - this command will be avaliable over http post request : /command/<your command name>
Rename class MyClickCommandProcessor for exclude class names clash.
Now you need to implement your specific page manipulations in process_command method over manipulations with [zendriver.Tab](https://github.com/stephanlensky/zendriver/blob/main/zendriver/core/tab.py).

What contains CustomUserCommands.py :
get_user_commands function : this method should return dictionary 'command name' => YourProcessor instance,
YourProcessor should be a class, that inherit BaseCommandProcessor,
and you need to override process_command method (like in CustomUserCommands.py),
this method should contains manipulations with page, that you need to make after challenge solving.
For manipulate with page you need to get driver specific page implementation over driver.get_driver, after that you have instance of [zendriver.Tab](https://github.com/stephanlensky/zendriver/blob/main/zendriver/core/tab.py)
and can use all operations of this class.

