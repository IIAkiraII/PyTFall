init -1 python:
    # GUI Logic ---------------------------------------------------------------------------------------------
    # One func:
    def point_in_poly(poly, x, y):

        n = len(poly)
        inside = False

        p1x, p1y = poly[0]
        for i in xrange(n+1):
            p2x, p2y = poly[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside


    class SlaveMarket(HabitableLocation):
        """
        Class for populating and running of the slave market.

        TODO sm/lt: (Refactor)
        Use actors container from Location class and
        """
        def __init__(self, type=None):
            """
            Creates a new SlaveMarket.
            type = type girls predominantly present in the market. Not used.
            """
            super(SlaveMarket, self).__init__(id="PyTFall Slavemarket")
            self.type = [] if type is None else type

            self.girl = None

            self.chars_list = None
            self.blue_girls = dict() # Girls (SE captured) blue is training for you.
            self.restock_day = locked_random("randint", 2, 3)

        def get_random_slaves(self):
            """
            Searches for chars to add to the slavemarket.
            """
            uniques = []
            randoms = []
            total = randint(9, 12)
            for c in chars.values():
                if c in hero.chars:
                    continue
                if c.home == self:
                    if c.__class__ == Char:
                        uniques.append(c)
                    if c.__class__ == rChar:
                        randoms.append(c)

            # # Do this thing proper in char gen! TODO
            # if len(randoms) < 10:
            #     for i in range(total-len(randoms)):
            #         if dice(1): # Super char!
            #             tier = hero.tier + uniform(3.0, 5.0)
            #         elif dice(20): # Decent char.
            #             tier = hero.tier + uniform(1.0, 2.5)
            #         else: # Ok char...
            #             tier = hero.tier + uniform(.2, 1.0)
            #
            #         bt_group = choice(["SIW", "Server"])
            #
            #         status = "slave"
            #         give_civilian_items = True
            #         give_bt_items = False
            #
            #         rc = build_rc(bt_group=bt_group,
            #                      set_locations=True,
            #                      set_status=status,
            #                      tier=tier, tier_kwargs=None,
            #                      give_civilian_items=give_civilian_items,
            #                      give_bt_items=give_bt_items,
            #                      spells_to_tier=False)
            #         randoms.append(rc)

            # Prioritize unique chars:
            slaves = random.sample(uniques, min(len(uniques), 7))
            slaves.extend(random.sample(randoms, min(len(randoms), total-len(slaves))))
            shuffle(slaves)
            return slaves

        @property
        def girlfin(self):
            """
            The property to return the proper financial data for the girl.
            """
            return self.girl.fin

        def populate_chars_list(self):
            """
            Populates the list of girls that are available.
            """
            self.chars_list = self.get_random_slaves()

        def next_day(self):
            """
            Solves the next day logic.
            """
            if self.restock_day == day:
                self.populate_chars_list()
                self.restock_day += locked_random("randint", 2, 3)

            for g in self.blue_girls.keys():
                self.blue_girls[g] += 1
                if self.blue_girls[g] == 30:
                    hero.add_char(g)
                    del self.blue_girls[g]
                    pytfall.temp_text.append("Blue has finished training %s! The girl has been delivered to you!" % chars[g].name)

        def next_index(self):
            """
            Sets the focus to the next girl.
            """
            if self.chars_list:
                index = self.chars_list.index(self.girl)
                index = (index + 1) % len(self.chars_list)
                self.girl = self.chars_list[index]

        def previous_index(self):
            """
            Sets the focus to the previous girl.
            """
            if self.chars_list:
                index = self.chars_list.index(self.girl)
                index = (index - 1) % len(self.chars_list)
                self.girl = self.chars_list[index]

        def set_index(self):
            """
            Sets the focus to a random girl.
            """
            if self.chars_list:
                self.girl = choice(self.chars_list)

        def set_girl(self, girl):
            """
            Sets the focus to the given girl.
            girl = The girl to set the focus to.
            """
            if self.chars_list and girl in self.chars_list:
                self.girl = girl


    class GuiHeroProfile(_object):
        '''The idea is to try and turn the while loop into the function
        I want girl_meets and quests to work in similar way
        This is basically practicing :)
        '''
        def __init__(self):
            self.show_item_info = False
            self.item = False

            self.finance_filter = "day"
            self.came_from = None # To enable jumping back to where we originally came from.

        def show_unequip_button(self):
            if self.item and self.item in hero.eqslots.values():
                return True

        def show_equip_button(self):
            if self.item and self.item.sex != "female" and self.item in hero.inventory:
                return True


    class PytGallery(_object):
        """
        PyTFall gallery to view girl's pictures and controls
        """
        def __init__(self, char):
            self.girl = char
            self.default_imgsize = (960, 660)
            self.imgsize = self.default_imgsize
            self.tag = "profile"
            self.tagsdict = tagdb.get_tags_per_character(self.girl)
            self.td_mode = "full" # Tagsdict Mode (full or dev)
            self.pathlist = list(tagdb.get_imgset_with_all_tags(set([char.id, "profile"])))
            self.imagepath = self.pathlist[0]
            self._image = self.pathlist[0]
            self.tags = " | ".join([i for i in tagdb.get_tags_per_path(self.imagepath)])

        def screen_loop(self):
            while 1:
                result = ui.interact()

                if result[0] == "image":
                    index = self.pathlist.index(self.imagepath)
                    if result[1] == "next":
                        index = (index + 1) % len(self.pathlist)
                        self.imagepath = self.pathlist[index]
                        self.set_img()

                    elif result[1] == "previous":
                        index = (index - 1) % len(self.pathlist)
                        self.imagepath = self.pathlist[index]
                        self.set_img()

                elif result[0] == "tag":
                    self.tag = result[1]
                    self.pathlist = list(tagdb.get_imgset_with_all_tags(set([self.girl.id, result[1]])))
                    self.imagepath = self.pathlist[0]
                    self.set_img()

                elif result[0] == "view_trans":
                    gallery.trans_view()

                # This is for the testing option (only in dev mode):
                elif result[0] == "change_dict":
                    if result[1] == "full":
                        self.td_mode = "full"
                        self.tagsdict = tagdb.get_tags_per_character(self.girl)
                    elif result[1] == "dev":
                        self.td_mode = "dev"
                        d = tagdb.get_tags_per_character(self.girl)
                        self.tagsdict = OrderedDict()
                        for i in d:
                            if i in ["portrait", "vnsprite", "battle_sprite"]:
                                self.tagsdict[i] = d[i]

                elif result[0] == "control":
                    if result[1] == 'return':
                        break

        @property
        def image(self):
            return ProportionalScale("/".join([self.girl.path_to_imgfolder, self._image]), self.imgsize[0], self.imgsize[1])

        def set_img(self):
            if self.tag in ("vnsprite", "battle_sprite"):
                self.imgsize = self.girl.get_sprite_size(self.tag)
            else:
                self.imgsize = self.imgsize

            self._image = self.imagepath
            self.tags = " | ".join([i for i in tagdb.get_tags_per_path(self.imagepath)])


        def trans_view(self):
            """
            I want to try and create some form of automated transitions/pics loading for viewing mechanism.
            Transitions are taken from Ceramic Hearts.
            """
            # Get the list of files for transitions first:
            transitions = list()
            path = content_path("gfx/masks")
            for file in os.listdir(path):
                if check_image_extension(file):
                    transitions.append("/".join([path, file]))
            transitions.reverse()
            transitions_copy = copy.copy(transitions)

            # Get the images:
            images = self.pathlist * 1
            shuffle(images)
            images_copy = copy.copy(images)

            renpy.hide_screen("gallery")
            renpy.with_statement(dissolve)

            renpy.show_screen("gallery_trans")

            renpy.music.play("content/sfx/music/reflection.mp3", fadein=1.5)

            global stop_dis_shit
            stop_dis_shit = False

            first_run = True

            while not stop_dis_shit:

                if not images:
                    images = images_copy * 1
                if not transitions:
                    transitions = transitions_copy * 1

                image = images.pop()
                image = "/".join([self.girl.path_to_imgfolder, image])
                x, y = renpy.image_size(image)
                rndm = randint(5, 7)
                if first_run:
                    first_run = False
                else:
                    renpy.hide(tag)
                tag = str(random.random())

                if x > y:
                    ratio = config.screen_height/float(y)
                    if int(round(x * ratio)) <= config.screen_width:
                        image = ProportionalScale(image, config.screen_width, config.screen_height)
                        renpy.show(tag, what=image, at_list=[truecenter, simple_zoom_from_to_with_linear(1.0, 1.5, rndm)])
                        renpy.with_statement(ImageDissolve(transitions.pop(), 3))
                        renpy.pause(rndm-3)
                    else:
                        image = ProportionalScale(image, 10000, config.screen_height)
                        renpy.show(tag, what=image, at_list=[move_from_to_align_with_linear((.0, .5), (1.0, .5), rndm)])
                        renpy.with_statement(ImageDissolve(transitions.pop(), 3))
                        renpy.pause(rndm-3)
                elif y > x:
                    ratio = 1366/float(x)
                    if int(round(y * ratio)) <= 768:
                        image = ProportionalScale(image, config.screen_width, config.screen_height)
                        renpy.show(tag, what=image, at_list=[truecenter, simple_zoom_from_to_with_linear(1.0, 1.5, rndm)])
                        renpy.with_statement(ImageDissolve(transitions.pop(), 3))
                        renpy.pause(rndm-3)
                    else:
                        image = ProportionalScale(image, config.screen_width, 10000)
                        renpy.show(tag, what=image, at_list=[truecenter, move_from_to_align_with_linear((.5, 1.0), (.5, .0), rndm)])
                        renpy.with_statement(ImageDissolve(transitions.pop(), 3))
                        renpy.pause(rndm-3)
                else:
                    image = ProportionalScale(image, config.screen_width, config.screen_height)
                    renpy.show(tag, what=image, at_list=[truecenter, simple_zoom_from_to_with_linear(1.0, 1.5, rndm)])
                    renpy.with_statement(ImageDissolve(transitions.pop(), 3))
                    renpy.pause(rndm-3)



            renpy.hide_screen("gallery_trans")
            renpy.music.stop(fadeout=1.0)
            renpy.hide(tag)
            renpy.show_screen("gallery")
            renpy.with_statement(dissolve)


    class CoordsForPaging(object):
        """ This class setups up x, y coordinates for items in content list.

        We use this in DragAndDrop.
        Might be I'll just use this in the future to handle the whole thing.
        For now, this will be used in combination with screen language.
        """
        def __init__(self, content, columns=2, rows=6, size=(100, 100), xspacing=10, yspacing=10, init_pos=(0, 0)):
            self.content = content
            self.page = 0
            self.page_size = columns*rows

            self.pos = list()
            x = init_pos[0]
            for c in xrange(columns):
                y = init_pos[1]
                for r in xrange(rows):
                    self.pos.append((x, y))
                    y = y + size[1] + yspacing
                x = x + size[0] + xspacing

        def __len__(self):
            return len(self.content)

        def __iter__(self):
            """We return a list of tuples of [(item, pos), (item, pos), ...]"""
            page = self.page_content
            pos = self.pos[:len(page)]
            return iter(zip(page, pos))

        def __getitem__(self, index):
            # Minding the page we're on!
            return self.content[self.page*self.page_size + index]

        def __nonzero__(self):
            return bool(self.content)

        def get_pos(self, item):
            """Retruns a pos of an item on current page"""
            return self.pos[self.page_content.index(item)]

        # Paging:
        def next_page(self):
            if self.max_page>0:
                self.page = (self.page + 1) % self.max_page
            else:
                self.page = 0

        def prev_page(self):
            if self.max_page>0:
                self.page = (self.page - 1) % self.max_page
            else:
                self.page = 0

        def last_page(self):
            self.page = self.max_page - 1 if self.paged_items else 0

        def first_page(self):
            self.page = 0

        @property
        def max_page(self):
            return len(self.paged_items)

        @property
        def paged_items(self):
            items = []
            for start in xrange(0, len(self.content), self.page_size):
                 items.append(self.content[start:start+self.page_size])
            return items

        @property
        def page_content(self):
            """Get content for current page"""
            items = self.paged_items

            try:
                return items[self.page]
            except IndexError:
                if self.page - 1 >= 0:
                    self.page -= 1
                    return items[self.page]
                else:
                    self.page = 0
                    return []

        def add(self, item):
            if item not in self.content:
                self.content.append(item)

        def remove(self, item):
            if item in self.content:
                self.content.remove(item)


    def dragged(drags, drop):
        # Simple func we use to manage drag and drop in team setups and maybe moar in the future.
        drag = drags[0]
        char = drag.drag_name
        x, y = workers.get_pos(char)

        if not drop:
            drag.snap(x, y, delay=.2)
            return

        team = drop.drag_name

        if char.status == "slave":
            drag.snap(x, y, delay=.4)
            renpy.show_screen("message_screen", "Slaves are not allowed to participate in combat!")
            renpy.restart_interaction()
            return

        if len(team) == 3:
            drag.snap(x, y, delay=.2)
            return
        else:
            team.add(char)
            workers.remove(char)
            drag.snap(x, y)
            return True
