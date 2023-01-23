import random
import asyncio
import re
import ast
import math
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from database.connections_mdb import active_connection, all_connections, delete_connection, if_active, make_active, make_inactive
from info import ADMINS, AUTH_CHANNEL, LOG_CHANNEL, SUPPORT_CHAT, SUPPORT_GROUP, PICS, AUTH_USERS, CUSTOM_FILE_CAPTION, AUTH_GROUPS, P_TTI_SHOW_OFF, IMDB, SINGLE_BUTTON, SPELL_CHECK_REPLY, IMDB_TEMPLATE
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid, ChatAdminRequired
from utils import get_size, is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings
from database.users_chats_db import db
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.filters_mdb import (
    del_all,
    find_filter,
    get_filters,
)
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

BUTTONS = {}
SPELL_CHECK = {}


@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    if message.chat.id == SUPPORT_GROUP:
        k = await manual_filters(client, message)
        if k == False:
            await auto_filter(client, message)
    else:
        if AUTH_CHANNEL and not await is_subscribed(client, message):
            try:
                invite_link = await client.create_chat_invite_link(int(AUTH_CHANNEL))
            except ChatAdminRequired:
                logger.error("Make sure Bot is admin in Forcesub channel")
                return
            buttons = [[
                InlineKeyboardButton("📢 Updates Channel 📢", url=invite_link.invite_link)
            ],[
                InlineKeyboardButton("🔁 Request Again 🔁", callback_data="grp_checksub")
            ]]
            reply_markup = InlineKeyboardMarkup(buttons)
            k = await message.reply_photo(
                photo=random.choice(PICS),
                caption=f"👋 Hello {message.from_user.mention},\n\nPlease join my 'Updates Channel' and request again. 😇",
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            await asyncio.sleep(300)
            await message.delete()
            await k.delete()
        else:
            k = await manual_filters(client, message)
            if k == False:
                await auto_filter(client, message)


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = BUTTONS.get(key)
    if not search:
        await query.answer(f"Hello {query.from_user.first_name},\nSend New Request Again!", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    settings = await get_settings(query.message.chat.id)
    if settings['button']:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"💥 {get_size(file.file_size)} 💫 {file.file_name}", callback_data=f'file#{file.file_id}'
                )
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"💥 {get_size(file.file_size)}",
                    callback_data=f'file#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"💫 {file.file_name}", callback_data=f'file#{file.file_id}'
                )
            ]
            for file in files
        ]
    btn.insert(0,
        [InlineKeyboardButton(f"✅ {search} ✅", callback_data="search")]
    )

    if 0 < offset <= 10:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - 10
    if n_offset == 0:

        btn.append(
            [InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
             InlineKeyboardButton(f"🗓 PAGES {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}",
                                  callback_data="page")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    elif off_set is None:
        btn.append(
            [InlineKeyboardButton(f"🗓 PAGES {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
             InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")])
    else:
        btn.append(
            [
                InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"),
                InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / 10) + 1} / {math.ceil(total / 10)}", callback_data="pages"),
                InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")
            ]
        )
        btn.append(
            [
                InlineKeyboardButton("❌ Close ❌", callback_data="close_data")
            ]
        )
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^spolling"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    if movie_ == "close_spellcheck":
        await query.answer("Closed Spell Check!")
        await query.message.reply_to_message.delete()
        return await query.message.delete()
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer(f"Hello {query.from_user.first_name},\nSend New Request Again!", show_alert=True)
    movie = movies[(int(movie_))]
    await query.answer('Checking For My Database...')
    k = await manual_filters(bot, query.message, text=movie)
    if k == False:
        files, offset, total_results = await get_search_results(movie, offset=0, filter=True)
        if files:
            k = (movie, files, offset, total_results)
            await auto_filter(bot, query, k)
        else:
            await bot.send_message(LOG_CHANNEL, script.NO_RESULT_TXT.format(query.message.chat.title, query.message.chat.id, query.from_user.mention, movie))
            k = await query.message.edit(f"👋 Hello {query.from_user.mention},\n\nI don't find <b>'{movie}'</b> in my database. 😔")
            await asyncio.sleep(60)
            await query.message.reply_to_message.delete()
            await k.delete()


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if query.data == "close_data":
        try:
            user = query.message.reply_to_message.from_user.id
            if int(user) != 0 and query.from_user.id != int(user):
                return await query.answer(f"Hello {query.from_user.first_name},\nThis Is Not For You!", show_alert=True)
            await query.answer("Closed!")
            await query.message.reply_to_message.delete()
            await query.message.delete()
        except:
            await query.answer("Closed!")
            await query.message.delete()
    elif query.data == "delallconfirm":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            grpid = await active_connection(str(userid))
            if grpid is not None:
                grp_id = grpid
                try:
                    chat = await client.get_chat(grpid)
                    title = chat.title
                except:
                    await query.message.edit_text("Make sure i'm present in your group!", quote=True)
                    return
            else:
                await query.message.edit_text(
                    "I'm not connected to any groups!\nCheck /connections or connect to any groups",
                    quote=True
                )
                return

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            title = query.message.chat.title

        else:
            return

        st = await client.get_chat_member(grp_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            await del_all(query.message, grp_id, title)
        else:
            await query.answer("This Is Not For You!", show_alert=True)
    elif query.data == "delallcancel":
        userid = query.from_user.id
        chat_type = query.message.chat.type

        if chat_type == enums.ChatType.PRIVATE:
            await query.message.reply_to_message.delete()
            await query.message.delete()

        elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            grp_id = query.message.chat.id
            st = await client.get_chat_member(grp_id, userid)
            if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
                await query.message.delete()
                try:
                    await query.message.reply_to_message.delete()
                except:
                    pass
            else:
                await query.answer("This Is Not For You!", show_alert=True)
    elif "groupcb" in query.data:

        group_id = query.data.split(":")[1]

        act = query.data.split(":")[2]
        hr = await client.get_chat(int(group_id))
        title = hr.title
        user_id = query.from_user.id

        if act == "":
            stat = "CONNECT"
            cb = "connectcb"
        else:
            stat = "DISCONNECT"
            cb = "disconnect"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{stat}", callback_data=f"{cb}:{group_id}"),
             InlineKeyboardButton("DELETE", callback_data=f"deletecb:{group_id}")],
            [InlineKeyboardButton("BACK", callback_data="backcb")]
        ])

        await query.message.edit_text(
            f"Group Name: **{title}**\nGroup ID: `{group_id}`",
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        return
    elif "connectcb" in query.data:

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title

        user_id = query.from_user.id

        mkact = await make_active(str(user_id), str(group_id))

        if mkact:
            await query.message.edit_text(
                f"Connected to **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text('Some error occurred!', parse_mode=enums.ParseMode.MARKDOWN)
        return
    elif "disconnect" in query.data:

        group_id = query.data.split(":")[1]

        hr = await client.get_chat(int(group_id))

        title = hr.title
        user_id = query.from_user.id

        mkinact = await make_inactive(str(user_id))

        if mkinact:
            await query.message.edit_text(
                f"Disconnected from **{title}**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return
    elif "deletecb" in query.data:

        user_id = query.from_user.id
        group_id = query.data.split(":")[1]

        delcon = await delete_connection(str(user_id), str(group_id))

        if delcon:
            await query.message.edit_text(
                "Successfully deleted connection"
            )
        else:
            await query.message.edit_text(
                f"Some error occurred!",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        return
    elif query.data == "backcb":

        userid = query.from_user.id

        groupids = await all_connections(str(userid))
        if groupids is None:
            await query.message.edit_text(
                "There are no active connections! Connect to some groups first.",
            )
            return
        buttons = []
        for groupid in groupids:
            try:
                ttl = await client.get_chat(int(groupid))
                title = ttl.title
                active = await if_active(str(userid), str(groupid))
                act = " - ACTIVE" if active else ""
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                        )
                    ]
                )
            except:
                pass
        if buttons:
            await query.message.edit_text(
                "Your connected group details:\n\n",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    elif "alertmessage" in query.data:
        grp_id = query.message.chat.id
        i = query.data.split(":")[1]
        keyword = query.data.split(":")[2]
        reply_text, btn, alerts, fileid = await find_filter(grp_id, keyword)
        if alerts is not None:
            alerts = ast.literal_eval(alerts)
            alert = alerts[int(i)]
            alert = alert.replace("\\n", "\n").replace("\\t", "\t")
            await query.answer(alert, show_alert=True)

    if query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        if not files_:
            return await query.answer('No Such File Exist!', show_alert=True)
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        settings = await get_settings(query.message.chat.id)
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"
    
        try:
            if AUTH_CHANNEL and not await is_subscribed(client, query):
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                return
            elif settings['botpm']:
                await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
                return
            else:
                await client.send_cached_media(
                    chat_id=query.from_user.id,
                    file_id=file_id,
                    caption=f_caption,
                    protect_content=True if ident == "filep" else False,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❤️‍🔥 Please Share and Support ❤️‍🔥', url=f'https://t.me/share/url?url=https://t.me/{temp.U_NAME}')]])
                )
                await client.send_message(chat_id=query.from_user.id, text=f"👋 Hello {query.from_user.mention},\n\nHappy Downloading and Come Again... ❤️")
                await query.answer(f"Hello {query.from_user.first_name},\nCheck Your Inbox!", show_alert=True)
        except UserIsBlocked:
            await query.answer(f'Hello {query.from_user.first_name},\nYour blocked me, Unblock me and try again...', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://t.me/{temp.U_NAME}?start={ident}_{file_id}")

    elif query.data.startswith("checksub"):
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer(f"Hello {query.from_user.first_name},\nI would like to try yours, Please join my update channel and try again.", show_alert=True)
            return
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('No Such File Exist!', show_alert=True)
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                logger.exception(e)
                f_caption = f_caption
        if f_caption is None:
            f_caption = f"{title}"
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption=f_caption,
            protect_content=True if ident == 'checksubp' else False,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❤️‍🔥 Please Share and Support ❤️‍🔥', url=f'https://t.me/share/url?url=https://t.me/{temp.U_NAME}')]])
        )
        await client.send_message(chat_id=query.from_user.id, text=f"👋 Hello {query.from_user.mention},\n\nHappy Downloading and Come Again... ❤️")

    elif query.data == "grp_checksub":
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nThis Is Not For You!", show_alert=True)
        if AUTH_CHANNEL and not await is_subscribed(client, query):
            await query.answer(f"Hello {query.from_user.first_name},\nI would like to try yours, Please join my update channel and request again.", show_alert=True)
            return
        await query.answer(f"Hello {query.from_user.first_name},\nGood, Can You Request Now!", show_alert=True)
        await query.message.reply_to_message.delete()
        await query.message.delete()

    elif query.data == "pages":
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        await query.answer(f"Hello {query.from_user.first_name},\nIf you don't see what you want on this page, Click on the next page.", show_alert=True)

    elif query.data == "page":
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        await query.answer(f"Hello {query.from_user.first_name},\nNo more pages available!", show_alert=True)

    elif query.data == "search":
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        await query.answer(f"Hello {query.from_user.first_name},\nClick the button below you want and start the bot.", show_alert=True)

    elif query.data == "start":
        await query.answer('Welcome!')
        buttons = [[
            InlineKeyboardButton("➕ Add Me To Your Group ➕", url=f'http://t.me/{temp.U_NAME}?startgroup=true')
        ],[
            InlineKeyboardButton('👑 My Owner 👑', callback_data='my_owner'),
            InlineKeyboardButton('ℹ️ My About ℹ️', callback_data='my_about')
        ],[
            InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "my_about":
        buttons = [[
            InlineKeyboardButton('Report Bugs and Feedback', url=SUPPORT_CHAT),
            InlineKeyboardButton('Bot Status', callback_data='bot_status')
        ],[
            InlineKeyboardButton('🏠 Home 🏠', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MY_ABOUT_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "my_owner":
        buttons = [[
            InlineKeyboardButton('🏠 Home 🏠', callback_data='start'),
            InlineKeyboardButton('Contact', url='https://t.me/Hansaka_Anuhas')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.MY_OWNER_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data == "bot_status":
        await query.answer("Refreshing Database...")
        buttons = [[
            InlineKeyboardButton('◀️ Back', callback_data='my_about')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        total = await Media.count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        monsize = await db.get_db_size()
        free = 536870912 - monsize
        monsize = get_size(monsize)
        free = get_size(free)
        await query.message.edit_text(
            text=script.BOT_STATUS_TXT.format(total, users, chats, monsize, free),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
    elif query.data.startswith("opn_pm_setgs"):
        ident, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return
        if str(grp_id) != str(grpid):
            await query.message.edit("You are not connected to the group! Please /connect group and then change /settings")
            return
        title = query.message.chat.title
        settings = await get_settings(grpid)
        btn = [[
            InlineKeyboardButton("⚡️ Go To Chat ⚡️", url=f"https://t.me/{temp.U_NAME}")
        ]]

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Filter Button',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Single' if settings["button"] else 'Double',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Bot Inbox', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["botpm"] else '❌ No',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]

            try:
                await client.send_message(
                    chat_id=userid,
                    text=f"Change your settings for <b>'{title}'</b> as your wish. ⚙",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
                await query.message.edit_text(f"Settings menu sent in private chat.")
                await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
            except UserIsBlocked:
                return await query.answer('Your blocked me, Unblock me and try again...', show_alert=True)

    elif query.data.startswith("opn_grp_setgs"):
        ident, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return
        if str(grp_id) != str(grpid):
            await query.message.edit("You are not connected to the group! Please /connect group and then change /settings")
            return
        title = query.message.chat.title
        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Filter Button',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Single' if settings["button"] else 'Double',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Bot Inbox', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["botpm"] else '❌ No',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                text=f"Change your settings for <b>'{title}'</b> as your wish. ⚙",
                parse_mode=enums.ParseMode.HTML
            )
            await query.message.edit_reply_markup(reply_markup)

    elif query.data.startswith("setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        grpid = await active_connection(str(query.from_user.id))
        userid = query.from_user.id if query.from_user else None
        st = await client.get_chat_member(grp_id, userid)
        if (
                st.status != enums.ChatMemberStatus.ADMINISTRATOR
                and st.status != enums.ChatMemberStatus.OWNER
                and str(userid) not in ADMINS
        ):
            await query.answer("This Is Not For You!", show_alert=True)
            return

        if str(grp_id) != str(grpid):
            await query.message.edit("You are not connected to the group! Please /connect group and then change /settings")
            return

        if status == "True":
            await save_group_settings(grpid, set_type, False)
        else:
            await save_group_settings(grpid, set_type, True)

        settings = await get_settings(grpid)

        if settings is not None:
            buttons = [
                [
                    InlineKeyboardButton('Filter Button',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}'),
                    InlineKeyboardButton('Single' if settings["button"] else 'Double',
                                         callback_data=f'setgs#button#{settings["button"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Bot Inbox', callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["botpm"] else '❌ No',
                                         callback_data=f'setgs#botpm#{settings["botpm"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('File Secure',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["file_secure"] else '❌ No',
                                         callback_data=f'setgs#file_secure#{settings["file_secure"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('IMDb Poster', callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["imdb"] else '❌ No',
                                         callback_data=f'setgs#imdb#{settings["imdb"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Spelling Check',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["spell_check"] else '❌ No',
                                         callback_data=f'setgs#spell_check#{settings["spell_check"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('Welcome Message', callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}'),
                    InlineKeyboardButton('✅ Yes' if settings["welcome"] else '❌ No',
                                         callback_data=f'setgs#welcome#{settings["welcome"]}#{str(grp_id)}')
                ],
                [
                    InlineKeyboardButton('❌ Close ❌', callback_data='close_data')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.answer("Changed!")
            await query.message.edit_reply_markup(reply_markup)

    elif query.data.startswith("show_options"):
        #ident, from_user = query.data.split("#")
        ident, msg_id = query.data.split('#')
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            #InlineKeyboardButton("✅ Accept ✅", callback_data=f"accept {from_user}")
        #],[
            InlineKeyboardButton("❌ Reject ❌", callback_data=f"reject#{msg_id}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("reject"):
        #ident, from_user = query.data.split("#")
        ident, msg_id = query.data.split("#")
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("❌ Reject ❌", callback_data=f"rj_alert")
        ]]
        btn = [[
            InlineKeyboardButton("View Status", url=f"{query.message.link}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            #user = await client.get_users(from_user)
            request = query.message.text
            await query.answer("Message sent requester")
            await query.message.edit_text(f"<s>{request}</s>")
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            #try:
                #await client.send_message(chat_id=from_user, text="Sorry your request is reject! ❌", reply_markup=InlineKeyboardMarkup(btn))
            #except UserIsBlocked:
                await client.send_message(SUPPORT_GROUP, text=f"👋 Hello {user.mention},\n\nSorry your request is reject! ❌", reply_markup=InlineKeyboardMarkup(btn), reply_to_message_id=msg_id)
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("accept"):
        ident, from_user = query.data.split("#")
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("❌ Not Available ❌", callback_data=f"not_available#{from_user}")
        ],[
            InlineKeyboardButton("✅ Uploaded ✅", callback_data=f"uploaded#{from_user}")
        ],[
            InlineKeyboardButton("🟢 Already Available 🟢", callback_data=f"already_available#{from_user}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("not_available"):
        ident, from_user = query.data.split("#")
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("❌ Not Available ❌", callback_data=f"na_alert#{from_user}")
        ]]
        btn = [[
            InlineKeyboardButton("View Status", url=f"{query.message.link}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            user = await client.get_users(from_user)
            request = query.message.text
            await query.answer("Message sent requester")
            await query.message.edit_text(f"<s>{request}</s>")
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            try:
                await client.send_message(chat_id=from_user, text="Sorry your request is not available! ❌", reply_markup=InlineKeyboardMarkup(btn))
            except UserIsBlocked:
                await client.send_message(SUPPORT_GROUP, text=f"👋 Hello {user.mention},\n\nSorry your request is not available! ❌", reply_markup=InlineKeyboardMarkup(btn))
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("uploaded"):
        ident, from_user = query.data.split("#")
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("✅ Uploaded ✅", callback_data=f"ul_alert#{from_user}")
        ]]
        btn = [[
            InlineKeyboardButton("View Status", url=f"{query.message.link}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            user = await client.get_users(from_user)
            request = query.message.text
            await query.answer("Message sent requester")
            await query.message.edit_text(f"<s>{request}</s>")
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            try:
                await client.send_message(chat_id=from_user, text="Your request is uploaded! ✅", reply_markup=InlineKeyboardMarkup(btn))
            except UserIsBlocked:
                await client.send_message(SUPPORT_GROUP, text=f"👋 Hello {user.mention},\n\nYour request is uploaded! ✅", reply_markup=InlineKeyboardMarkup(btn))
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("already_available"):
        ident, from_user = query.data.split("#")
        channel_id = query.message.chat.id
        userid = query.from_user.id
        buttons = [[
            InlineKeyboardButton("🟢 Already Available 🟢", callback_data=f"aa_alert#{from_user}")
        ]]
        btn = [[
            InlineKeyboardButton("View Status", url=f"{query.message.link}")
        ]]
        st = await client.get_chat_member(channel_id, userid)
        if (st.status == enums.ChatMemberStatus.ADMINISTRATOR) or (st.status == enums.ChatMemberStatus.OWNER):
            user = await client.get_users(from_user)
            request = query.message.text
            await query.answer("Message sent requester")
            await query.message.edit_text(f"<s>{request}</s>")
            await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
            try:
                await client.send_message(chat_id=from_user, text="Your request is already available! 🟢", reply_markup=InlineKeyboardMarkup(btn))
            except UserIsBlocked:
                await client.send_message(SUPPORT_GROUP, text=f"👋 Hello {user.mention},\n\nYour request is already available! 🟢", reply_markup=InlineKeyboardMarkup(btn))
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("rj_alert"):
        ident, from_user = query.data.split("#")
        userid = query.from_user.id
        if str(userid) in from_user:
            await query.answer("Sorry your request is reject!", show_alert=True)
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("na_alert"):
        ident, from_user = query.data.split("#")
        userid = query.from_user.id
        if str(userid) in from_user:
            await query.answer("Sorry your request is not available!", show_alert=True)
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("ul_alert"):
        ident, from_user = query.data.split("#")
        userid = query.from_user.id
        if str(userid) in from_user:
            await query.answer("Your request is uploaded!", show_alert=True)
        else:
            await query.answer("This Is Not For You!", show_alert=True)

    elif query.data.startswith("aa_alert"):
        ident, from_user = query.data.split("#")
        userid = query.from_user.id
        if str(userid) in from_user:
            await query.answer("Your request is already available!", show_alert=True)
        else:
            await query.answer("This Is Not For You!", show_alert=True)

async def auto_filter(client, msg, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        if message.text.startswith("/"): return  # ignore commands
        if re.findall("((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if 2 < len(message.text) < 100:
            search = message.text
            files, offset, total_results = await get_search_results(search.lower(), offset=0, filter=True)
            if not files:
                if settings["spell_check"]:
                    return await advantage_spell_chok(msg)
                else:
                    return
        else:
            return
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
    pre = 'filep' if settings['file_secure'] else 'file'
    if settings["button"]:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"💥 {get_size(file.file_size)} 💫 {file.file_name}", callback_data=f'{pre}#{file.file_id}'
                )
            ]
            for file in files
        ]
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=f"💥 {get_size(file.file_size)}",
                    callback_data=f'{pre}#{file.file_id}',
                ),
                InlineKeyboardButton(
                    text=f"💫 {file.file_name}",
                    callback_data=f'{pre}#{file.file_id}',
                )
            ]
            for file in files
        ]
    btn.insert(0,
        [InlineKeyboardButton(f"✅ {search} ✅", callback_data="search")]
    )

    if offset != "":
        key = f"{message.chat.id}-{message.id}"
        BUTTONS[key] = search
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [InlineKeyboardButton(text=f"🗓 PAGES 1 / {math.ceil(int(total_results) / 10)}", callback_data="pages"),
             InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="🗓 PAGES 1 / 1", callback_data="page")]
        )
        btn.append(
            [InlineKeyboardButton("❌ Close ❌", callback_data="close_data")]
        )
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    if imdb:
        cap = IMDB_TEMPLATE.format(
            query=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
    else:
        cap = f"✅ I Found: <code>{search}</code>\n\n🗣 Requested by: {message.from_user.mention}\n©️ Powered by: <b>{message.chat.title}</b>"
    if imdb and imdb.get('poster'):
        try:
            await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024],
                                          reply_markup=InlineKeyboardMarkup(btn))
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            await message.reply_photo(photo=poster, caption=cap[:1024], reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            logger.exception(e)
            await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    else:
        if message.chat.id == SUPPORT_GROUP:
            buttons = [[InlineKeyboardButton('✨ Our Group ✨', url='https://t.me/SL_Films_World')]]
            await message.reply_text(text=f"👋 Hello {message.from_user.mention},\n\n✅ I Found: {search}\n💯 Total Results: <code>{total_results}</code>\n\nAvailable In 👇", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await message.reply_text(cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
    if spoll:
        await msg.message.delete()


async def advantage_spell_chok(msg):
    search = msg.text
    search_google = search.replace(" ", "+")
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)  # plis contribute some common words
    query = query.strip() + " movie"
    g_s = await search_gagala(query)
    g_s += await search_gagala(msg.text)
    gs_parsed = []
    if not g_s:
        btn = [[InlineKeyboardButton("🔎 Search Google 🔍", url=f"https://www.google.com/search?q={search_google}")]]
        k = await msg.reply_photo(photo=random.choice(PICS), caption=f"👋 Hello {msg.from_user.mention},\n\nI can't find <b>'{search}'</b> you requested. 😢</b>", reply_markup=InlineKeyboardMarkup(btn))
        await asyncio.sleep(60)
        await msg.delete()
        await k.delete()
        return
    regex = re.compile(r".*(imdb|wikipedia).*", re.IGNORECASE)  # look for imdb / wiki results
    gs = list(filter(regex.match, g_s))
    gs_parsed = [re.sub(
        r'\b(\-([a-zA-Z-\s])\-\simdb|(\-\s)?imdb|(\-\s)?wikipedia|\(|\)|\-|reviews|full|all|episode(s)?|film|movie|series)',
        '', i, flags=re.IGNORECASE) for i in gs]
    if not gs_parsed:
        reg = re.compile(r"watch(\s[a-zA-Z0-9_\s\-\(\)]*)*\|.*",
                         re.IGNORECASE)  # match something like Watch Niram | Amazon Prime
        for mv in g_s:
            match = reg.match(mv)
            if match:
                gs_parsed.append(match.group(1))
    user = msg.from_user.id if msg.from_user else 0
    movielist = []
    gs_parsed = list(dict.fromkeys(gs_parsed))  # removing duplicates
    if len(gs_parsed) > 3:
        gs_parsed = gs_parsed[:3]
    if gs_parsed:
        for mov in gs_parsed:
            imdb_s = await get_poster(mov.strip(), bulk=True)  # searching each keyword in imdb
            if imdb_s:
                movielist += [movie.get('title') for movie in imdb_s]
    movielist += [(re.sub(r'(\-|\(|\)|_)', '', i, flags=re.IGNORECASE)).strip() for i in gs_parsed]
    movielist = list(dict.fromkeys(movielist))  # removing duplicates
    if not movielist:
        btn = [[InlineKeyboardButton("🔎 Search Google 🔍", url=f"https://www.google.com/search?q={search_google}")]]
        k = await msg.reply_photo(photo=random.choice(PICS), caption=f"👋 Hello {msg.from_user.mention},\n\nI can't find the <b>'{search}'</b> you requested, Check if your spellings are correct. 😉", reply_markup=InlineKeyboardMarkup(btn))
        await asyncio.sleep(60)
        await msg.delete()
        await k.delete()
        return
    SPELL_CHECK[msg.id] = movielist
    btn = [[
        InlineKeyboardButton(
            text=movie.strip(),
            callback_data=f"spolling#{user}#{k}",
        )
    ] for k, movie in enumerate(movielist)]
    btn.append([InlineKeyboardButton(text="❌ Close ❌", callback_data=f'spolling#{user}#close_spellcheck')])
    k = await msg.reply_photo(photo=random.choice(PICS), caption=f"👋 Hello {msg.from_user.mention},\n\nI couldn't find the <b>'{search}'</b> you requested.\nDid you mean one of these? 👇",
                    reply_markup=InlineKeyboardMarkup(btn))
    await asyncio.sleep(300)
    await msg.delete()
    await k.delete()


async def manual_filters(client, message, text=False):
    group_id = message.chat.id
    name = text or message.text
    reply_id = message.reply_to_message.id if message.reply_to_message else message.id
    keywords = await get_filters(group_id)
    for keyword in reversed(sorted(keywords, key=len)):
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, name, flags=re.IGNORECASE):
            reply_text, btn, alert, fileid = await find_filter(group_id, keyword)

            if reply_text:
                reply_text = reply_text.replace("\\n", "\n").replace("\\t", "\t")

            if btn is not None:
                try:
                    if fileid == "None":
                        if btn == "[]":
                            await client.send_message(
                                group_id, 
                                reply_text, 
                                disable_web_page_preview=True,
                                reply_to_message_id=reply_id)
                        else:
                            button = eval(btn)
                            await client.send_message(
                                group_id,
                                reply_text,
                                disable_web_page_preview=True,
                                reply_markup=InlineKeyboardMarkup(button),
                                reply_to_message_id=reply_id
                            )
                    elif btn == "[]":
                        await client.send_cached_media(
                            group_id,
                            fileid,
                            caption=reply_text or "",
                            reply_to_message_id=reply_id
                        )
                    else:
                        button = eval(btn)
                        await message.reply_cached_media(
                            fileid,
                            caption=reply_text or "",
                            reply_markup=InlineKeyboardMarkup(button),
                            reply_to_message_id=reply_id
                        )
                except Exception as e:
                    logger.exception(e)
                break
    else:
        return False
