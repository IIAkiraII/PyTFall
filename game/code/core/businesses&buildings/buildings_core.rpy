init -10 python:
    #################################################################
    # CORE BUILDING CLASSES
    # BaseBuilding = Base class, needed if no other.
    # FamousBuilding = Adds fame and reputation mechanics to the building.
    # BuildingStats = Adds dirt and cleaning to the building.
    # UpgradableBuilding = Adds upgrades  to the building.
    #
    # Examples:
    # class CityJail(Building): <-- Just a building
    # class Brothel(UpgradableBuilding, BuildingStats, FamousBuilding): <-- A building will upgrade, dirt and fame mechanics.
    #
    """Core order for SimPy jobs loop:
    ***Needs update after restructuring/renaming.

    BUILDING:
        # Holds Businesses and data/properties required for operation.
        run_nd():
            # Setups and starts the simulation.
            *Generates Clients if required.
            *Builds worker lists.
            *Logs the init data to the building report.
            *Runs pre_day for all businesses.
            *Creates SimPy Environment and runs it (run_jobs being the main controlling process)
            *Runs the post_nd.
        building_manager():
            SimPy process that manages the building as a whole.
            # Main controller for all businesses.
            *Builds a list of all workable businesses.
            *Starts business_manager for each building.
        clients_manager():
            SimPy Process that supplies clients to the businesses within the building as required.
            *Adds a steady/conditioned stream of clients to the appropriate businesses and manages that stream:
            *Kicks clients if nothing could be arranged for them.

    BUSINESS:
        # Hold all data/methods required for business to operate.
        *Personal Service:
            - Finds best client match using update.get_workers()
            - Runs the job.
        *Public Service:
            - Simply sends client to business.
            - Sends in Workers to serve/entertain the clients.
        *OnDemand Service:
            - Includes some form of "on demand" service, like cleaning or guarding (defending).
            - May also have a continued, "automatic" service like Guard-patrol.

        *workers = On duty characters.
        *habitable/workable = self-explanotory.
        *clients = clients used locally (maybe useful only for the public service?)
        *capacity = cap of the building such as amount of rooms/workspace.
        *jobs = only for businesses
        *get_workers:
            - Checks if a char is capable.
            - Checks if a char is willing.
            - Can also try to match find the best client for the job.

        # This may be obsolete after refactoring... to be rewritten or deleted after a steady system is in place.
        SimPy Land:
            *res = Resource
            *time = cycle
            *is_running = May be useless

        *Personal Service:
            *find_best_match = finds a best client/worker combination.
            *request_resource:
                - requests a room for worker/client.
                - adds a run_job process to Env
                - logs it all to building log
            *run_job:
                - Waits for self.time delay
                - Calls the job so it can form an NDEvent

        *Public Service:
            *active_workers = Does this not simply double the normal workers?
            *request = plainly adds a client and keeps it in the business based on "ready_to_leave" flag set directly to the client.
            *add_worker:
                # Adds workers to business to serve clients.
                - Checks willingness to do the job.
                - Adds workers as required.
                - self.env.process(self.worker_control(worker)) Possible the most important part, this adds a process to Env.
                - Removes worker from building in order to reserve her for this business
            *run_job:
                # main method/SimPy event that manages the job from start to end.
                - Runs for as long there are active workers
                - Waits for self.time delay
                - Manages clients in the business
            *worker_control:
                # Env Process, manages each individual worker.
                - Runs while there are clients and worker has AP in self.time delays.
                - Logs all active clients as flags to a worker.
                - Logs tips to the worker.
                - Runs the Job once AP had been exhausted or there are no more clients availible.
                - Removes the worker from active workers

    Job:
        Has been completely restructured to server as an object to keep track
        of what character is doing what by direct binding and hosting loose
        functions.
    """


    class BaseBuilding(HabitableLocation, Flags):
        """The super class for all Building logic.
        """
        def __init__(self, id=None, name=None, desc=None,
                     price=100, mod=1, **kwargs):
            """Creates a new building.

            id = The id of the building.
            name = The name of the building.
            desc = The description of the building.
            price = The price of the building.
            mod = The modifier for the building.
            **kwargs = Excess arguments.
            """
            super(BaseBuilding, self).__init__(id=id)
            Flags.__init__(self)

            self.name = name
            self.desc = desc
            self._price = price
            self.price_overload = None

            self.jobs = set()
            self.building_jobs = set()

            # Flagging:
            self.flag_red = False
            self.flag_green = False
            self.highlighted = False

            # Rooms
            self.mod = mod

            # Security:
            self.security_rating = 0
            self.security_presence = 0

            self.tier = 0

            # Location Default:
            self.location = "Flee Bottom"

            # ND Report
            self.txt = ""

        def __str__(self):
            if self.name:
                return str(self.name)
            return super(BaseBuilding, self).__str__()

        @property
        def price(self):
            # Returns our best guess for price of the Building
            # Needed for buying, selling the building or for taxation.
            # **We may want to take reputation and fame into account as well.
            if self.price_overload is not None:
                return self.price_overload

            price = self._price

            if hasattr(self, "_upgrades"):
                for u in self._upgrades:
                    price += u.get_price()
            if hasattr(self, "_businesses"):
                for b in self._businesses:
                    price += b.get_price()
            return price

        @price.setter
        def price(self, value):
            self._price = value

        def get_price(self):
            return self.price

        def get_workers(self):
            # I may want better handing for this...
            # Returns a list of all chars in heros service that have their workplaces set to this building.
            return [c for c in hero.chars + [hero] if c.workplace==self and c.is_available]

        def get_all_chars(self):
            all_chars = set()

            for c in hero.chars:
                if not c.is_available:
                    continue
                if c.home == self:
                    all_chars.add(c)
                    continue
                if c.workplace == self:
                    all_chars.add(c)

            # if self.manager:
            #     all_chars.add(self.manager)

            return all_chars

        def get_girls(self, action=undefined, occupation=undefined, nott=False):
            """
            The girls that are in this location.
            action = The type of action the girls are doing.
            occupation = The occupation of the girls.
            nott = Whether to negate the selection.

            Note: undefined is used as an alternative to None, as a girl can have no action.
            Used by School, should be refactored out of all modern code now.
            """
            # Get all girls
            if action is undefined:
                g = [girl for girl in hero.chars if girl.location is self]

            # Only get girls that (don't) match action list
            elif isinstance(action, (list,tuple)):
                g = [girl for girl in hero.chars if girl.location is self and (girl.action in action) != nott]

            # Only get girls that are training
            elif action == "Course":
                g = [girl for girl in hero.chars if girl.location is self and isinstance(girl.action, basestring) and girl.action.endswith("Course") != nott]

            # Only get girls with specific action
            else:
                g = [girl for girl in hero.chars if girl.location is self and (girl.action == action) != nott]

            # Get all girls
            if occupation is undefined:
                return g

            # Only get girls that (don't) match occupation list
            elif isinstance(occupation, (list,tuple)):
                return [girl for girl in g if [tr for tr in girl.occupations if tr in occupation] != nott]

            # Only get girls with specific occupation
            else:
                return [girl for girl in g if (occupation in girl.occupations) != nott]


    class FamousBuilding(BaseBuilding):
        """A Building that has Fame and Reputation properties.

        Concept:
            fame should be difficult to gain and difficult to lose. Mostly,
                this decides how many client will come to the building.
            rep should be relatively easy to gain and easy to lose. Mostly,
                this decided the 'quality' (tier) of clients.
        """
        def __init__(self, *args, **kwargs):
            """
            Creates a new FamousBuilding.
            minfame = The minimum amount of fame the building can have.
            maxfame = The maximum amount of fame the building can have.
            minrep = The minimum amount of reputation the building can have.
            maxrep = The maximum amount of reputation the building can have.
            """
            super(FamousBuilding, self).__init__(*args, **kwargs)

            self.minfame = kwargs.pop("minfame", 0)
            self.maxfame = kwargs.pop("maxfame", 0)
            self.fame = self.minfame

            self.minrep = kwargs.pop("minrep", 0)
            self.maxrep = kwargs.pop("maxrep", 0)
            self.rep = self.minrep

        @property
        def fame_percentage(self):
            fame = self.fame*100.0/max(1, self.maxfame)
            return round_int(fame)

        @property
        def rep_percentage(self):
            rep = self.rep*100.0/max(1, self.maxrep)
            return round_int(rep)

        def modfame(self, value):
            """
            Changes how famous this building is.
            value = The amount to change.
            """
            if self.fame+value > self.maxfame:
                self.fame = self.maxfame
                return

            if value < 0:
                if self.fame+value < self.minfame:
                    self.fame = self.minfame
                    return

            self.fame += value

        def modrep(self, value):
            """
            Changes how reputable this building is.
            value = The amount to change.
            """
            if self.rep+value > self.maxrep:
                self.rep = self.maxrep
                return

            if value < 0:
                if self.rep+value < self.minrep:
                    self.rep = self.minrep
                    return

            self.rep += value


    class BuildingStats(_object):
        """
        A building that has stats (dirt/security) and underlying mechanics.
        """

        DIRT_STATES = dict(Immaculate=(0, 10), Sterile=(10, 20),
                           Spotless=(20, 30), Clean=(30, 40),
                           Tidy=(40, 50), Messy=(50, 60),
                           Dirty=(60, 70), Grimy=(70, 80),
                           Filthy=(80, 90), Disgusting=(90, 100))

        def __init__(self):
            """
            Creates a new BuildingStats.
            """
            self.stats = {"dirt": 0, "threat": 0}
            self.max_stats = {"dirt": 1000, "threat": 1000}
            self.auto_clean = False

            # Logging stat changes during the day:
            self.stats_log = {}

        @property
        def threat_mod(self):
            # Figure out threat mod to apply over the building every 25 DU!
            if self.location == "Flee Bottom":
                threat = 5
            elif self.location == "Midtown":
                threat = 2
            elif self.location == "Richford":
                threat = -1
            else:
                raise Exception("{} Building with an unknown location detected!".format(str(self)))

            return threat

        def __setattr__(self, key, value):
            stats = self.__dict__.get("stats", {})
            if key in stats:
                max_val = self.__dict__["max_stats"][key]
                if value > max_val:
                    stats[key] = max_val
                elif value < 0:
                    stats[key] = 0
                else:
                    stats[key] = value
            else:
                super(BuildingStats, self).__setattr__(key, value)

        def __getattr__(self, item):
            stats = self.__dict__.get("stats", {})
            if item in stats:
                return stats[item]
            raise AttributeError("%s object has no attribute named %r" %
                                (self.__class__.__name__, item))

        def get_cleaning_price(self):
            """
            How much it costs to clean this building.
            """
            dirt = self.dirt
            price = 10 + dirt + dirt
            return round_int(price)

        def get_threat_percentage(self):
            """
            Returns percentage of dirt in the building as (percent, description).
            """
            if self.threat < 0:
                self.threat = 0
            threat = self.threat * 100 / self.max_stats["threat"]
            if threat > 100:
                threat = 100

            return threat

        def get_dirt_percentage(self):
            """
            Returns percentage of dirt in the building as (percent, description).
            """
            if self.dirt < 0:
                self.dirt = 0
            dirt = self.dirt * 100 / self.max_stats["dirt"]
            if dirt > 100:
                dirt = 100

            dirt_string = ""
            for key in self.DIRT_STATES:
                if dirt >= self.DIRT_STATES[key][0] and dirt <= self.DIRT_STATES[key][1]:
                    dirt_string = key

            if not dirt_string:
                raise Exception, "No valid string for dirt percentage of %s was found!" % self.id

            return round_int(dirt), dirt_string

        def clean(self, value):
            result = self.dirt + value
            self.dirt = result
            if self.env:
                simpy_debug("{}: Clean Function: result: {}, self.dirt: {}".format(self.env.now, result, self.dirt))

        def nd_log_stats(self):
            # Get a list of stats, usually all 4.
            diff = OrderedDict()
            stats = self.stats.keys()
            if isinstance(self, FamousBuilding):
                # throw in fame and rep:
                stats.extend(["fame", "rep"])
            stats.sort()

            # Do not run the very first time:
            if self.stats_log:
                for stat in stats:
                    value = round_int(getattr(self, stat) - self.stats_log.get(stat, 0))
                    diff[stat] = value

            # Log the new values:
            for stat in stats:
                self.stats_log[stat] = getattr(self, stat)

            return diff


    class AdvertableBuilding(_object):
        # Devnote: clumsy and outdated...
        def add_adverts(self, adverts):
            if not hasattr(self, "_adverts"):
                self._adverts = []

            for adv in adverts:
                adv = deepcopy(adv)
                adv['active'] = False
                if not 'price' in adv:
                    adv['price'] = 0
                if not 'upkeep' in adv:
                    adv['upkeep'] = 0
                self._adverts.append(adv)

        @property
        def adverts(self):
            return self._adverts

        @property
        def can_advert(self):
            return bool(self._adverts)


    class UpgradableBuilding(BaseBuilding):
        def __init__(self, *args, **kwargs):
            """
            @ Last review:
            Alex: I've moved everything except adverts and methods from Building class here.
            """
            super(UpgradableBuilding, self).__init__(*args, **kwargs)
            self._upgrades = list()
            self.allowed_upgrades = []
            self._businesses = list()
            self.allowed_businesses = []

            # We add allowed BUs here, for businesses that have not been built yet.
            # { business: ["u1", "u2", ...]}
            self.allowed_business_upgrades = {}

            self.fin = Finances(self)

            # And new style upgrades:
            self.in_slots = 0 # Interior Slots
            self.in_slots_max = kwargs.pop("in_slots_max", 100)
            self.ex_slots = 0 # Exterior Slots
            self.ex_slots_max = kwargs.pop("ex_slots_max", 100)

            # We keep maximum amounts of workers of specific types that this business can hold in this dict.
            # They are kept as k/v pairs of Job(): amount.
            # If absent for any job available at the building, we assume that worker can be added endlessly.
            self.worker_slots_max = {}

            # BAD Code?, right now all jobs are kept in .jobs attribute...
            # if this is not a useful distinction, we remove this and just work with the jobs set.
            if hasattr(self, "building_jobs"):
                self.building_jobs = self.building_jobs.union(self.building_jobs)

            if kwargs.get("needs_management", True):
                self.add_job(simple_jobs["Manager"])
                self.worker_slots_max[simple_jobs["Manager"]] = 1
                self.normalize_jobs()

            # Clients:
            self.all_clients = set() # All clients of this building are maintained here.
            self.regular_clients = set() # Subset of self.all_clients.
            self.clients = set() # temp clients, this is used during SimPy cals and reset on when that ends.
            self.logged_clients = False
            # This is the amount of clients that will visit the Building:
            self.total_clients = 0 # this is set by get_client_count method.
            self.clients_regen_day = 0

            # Chars:
            # Note: We also use .inhabitants set inherited from all the way over location.
            self.manager = None
            self.manager_effectiveness = 0 # Calculated once (performance)
            # Bit of an issue could be that we're using all_workers in SimPy as well? :D
            # TODO (bb) Look into the above.
            self.all_workers = list() # All workers presently assigned to work in this building.
            self.available_workers = list() # This is built and used during the next day (SimPy).

            # Upgrades:
            self.nd_ups = list() # Upgrades active during the next day...

            # SimPy and etc follows:
            self.env = None

            self.mod = kwargs.get("mod", 1)

        def log(self, item, add_time=False):
            # Logs the item (text) to the Building log...
            # if add_time and self.env:
            #     item = "{}: ".format(self.env.now) + item
            self.nd_events_report.append(item)
            if DSNBR:
                devlog.info(item)

        # Jobs Related:
        def add_job(self, job):
            # Adds Job to the BUILDING! and normalizes it.
            self.building_jobs.add(job)
            self.normalize_jobs()

        def normalize_jobs(self):
            self.jobs = self.jobs.union(self.building_jobs)
            for up in self._businesses:
                self.jobs = self.jobs.union(up.jobs)

        def get_valid_jobs(self, char):
            """Returns a list of jobs available for the building that the character might be willing to do.

            Returns an empty list if no jobs is available for the character.
            """
            jobs = []

            for job in self.jobs:
                # We need to check if there are any slots for a worker are left:
                if job in self.worker_slots_max:
                    # we get a list of all workers that are assigned for this job:
                    temp = [w for w in self.all_workers if w.action == job or w.previousaction == job]
                    # This isn't bulletproof... we prolly want to access building.manager here...
                    if len(temp) >= self.worker_slots_max[job]:
                        continue
                if job.is_valid_for(char):
                    jobs.append(job)

            return jobs

        # Building of Upgrades:
        # This should be part of the main BUILDING!!! (So it's this one :) )
        # This will not be in use until we allow BUILDING the Buildings :D
        # def check_resources(self, upgrade):
        #     # checks if the player has enough resources to build an upgrade:
        #     return True
        #
        # def check_space(self, upgrade):
        #     # Checks if the main building has enough space to add this upgrade:
        #     return True
        #
        # def start_construction(self, upgrade):
        #     # Take the metarials (if we got here, it is assumed that player has enough of everything)
        #     for r in upgrade.MATERIALS:
        #         pass
        #
        #     # Cash...
        #     hero.take_money(upgrade.cost, "Building Upgrades")
        #
        #     # adds the upgrade to in construction buildings:
        #     self.in_construction_upgrades.append(upgrade)

        def get_extension_cost(self, extension, **ec_kwargs):
            # We figure out what it would take to add this extension (building or business)
            # using it's class attributes to figure out the cost and the materials required.
            tier = self.tier or 1

            if isclass(extension):
                ext = extension(**ec_kwargs)
            else:
                ext = extension
            if ext.building is None:
                ext.building = self

            cap = ext.capacity

            cost = ext.get_price()

            materials = ext.materials.copy()
            for k, v in materials.items():
                materials[k] = round_int(v*min(tier, 4))

            in_slots = ext.in_slots + cap*ext.exp_cap_in_slots
            ex_slots = ext.ex_slots + cap*ext.exp_cap_ex_slots

            return cost, materials, in_slots, ex_slots

        def eval_extension_build(self, extension_class, price=None):
            # If price is not None, we expect a tuple with requirements to build
            # Check if we can build an upgrade:
            if price is None:
                cost, materials, in_slots, ex_slots = self.get_extension_cost(extension_class)
            else:
                cost, materials, in_slots, ex_slots = price

            if (self.in_slots_max - self.in_slots) < in_slots or (self.ex_slots_max - self.ex_slots) < ex_slots:
                return False

            if self.has_extension(extension_class):
                return False

            if hero.gold < cost:
                return False

            for i, a in materials.iteritems():
                if hero.inventory[i] < a:
                    return False

            return True

        def pay_for_extension(self, cost, materials):
            # This does assume that we checked and know that MC has the resources.
            if cost:
                hero.take_money(cost, "Building Upgrades")

            if materials:
                for item, amount in materials.items():
                    hero.remove_item(item, amount)

        def add_business(self, business, normalize_jobs=True, pay=False):
            """Add business to the building.
            """
            cost, materials, in_slots, ex_slots = self.get_extension_cost(business)
            self.in_slots += in_slots
            self.ex_slots += ex_slots

            if pay:
                self.pay_for_extension(cost, materials)

            business.building = self
            self._businesses.append(business)
            self._businesses.sort(key=attrgetter("SORTING_ORDER"), reverse=True)

            # Add possible upgrades:
            cls_name = business.__class__.__name__
            upgrades = self.allowed_business_upgrades.get(cls_name, None)
            if upgrades is not None:
                for u in upgrades:
                    u = getattr(store, u)
                    if u not in business.allowed_upgrades:
                        business.allowed_upgrades.append(u)

            if normalize_jobs:
                self.normalize_jobs()

        def add_upgrade(self, upgrade, pay=False):
            cost, materials, in_slots, ex_slots = self.get_extension_cost(upgrade)
            self.in_slots += in_slots
            self.ex_slots += ex_slots

            if pay:
                self.pay_for_extension(cost, materials)

            upgrade.building = self
            self._upgrades.append(upgrade)
            self._upgrades.sort(key=attrgetter("SORTING_ORDER"), reverse=True)

        def all_possible_extensions(self):
            # Returns a list of all possible extensions (businesses and upgrades)
            return self.allowed_businesses + self.allowed_upgrades

        def all_extensions(self):
            return self._businesses + self._upgrades

        def has_extension(self, extension, include_business_upgrades=False):
            if not isclass(extension):
                extension = extension.__class__

            for ex in self.all_extensions():
                if isinstance(ex, extension):
                    return True

            if include_business_upgrades:
                for ex in self.all_extensions():
                    if ex.has_extension(extension):
                        return True

            return False

        def get_business(self, up):
            # Takes a string as an argument
            if up == "fg":
                temp = [u for u in building._businesses if u.__class__ == ExplorationGuild]
                if temp:
                    return temp[0]
                else:
                    return False

        # Describing building purposes:
        @property
        def habitable(self):
            # Overloads property of Location core class to serve the building.
            return any(i.habitable for i in self._businesses)

        @property
        def vacancies(self):
            # check if there is place to live in this building.
            if not self.habitable:
                return 0

            habitable = [i for i in self._businesses if i.habitable]
            capacity = sum([i.capacity for i in habitable])
            rooms = capacity - len(self.inhabitants)
            if rooms < 0:
                rooms = 0
            return rooms

        @property
        def workable(self):
            """Returns True if this building has upgrades that are businesses.
            """
            return any(i.workable for i in self._businesses)

        @property
        def capacity(self):
            # Full capacity, habitable and workable:
            capacity = 0

            workable = [i for i in self._businesses if i.workable]
            if workable:
                capacity = sum([i.capacity for i in workable])

            habitable = [i for i in self._businesses if i.habitable]
            if habitable:
                capacity = sum([i.capacity for i in habitable])
            return capacity

        # Clients related:
        def get_client_count(self, write_to_nd=False):
            """Get the amount of clients that will visit the building the next day.

            Weakness of this method atm is this:
                We only get 70% of total possible clients from businesses,
                    to make extensions meaningful.
                We do not make any distinctions between businesses we generate clients for.
                    This makes having businesses that attract loads of clients
                    hugely favorable to have when running a business that does not.
            """
            clients = .0

            if not any(a['name'] == 'Sign' and a['active'] for a in self.adverts):
                min_clients = -1
                if write_to_nd:
                    self.log("{}".format(set_font_color("You may want to put up a sign!\n", "red")))
                    self.flag_red = True
            else:
                min_clients = 2 # We expect at least two walk-ins otherwise.

            # if DSNBR: # DEBUGMODE:
            #     debug_add = 10
            #     devlog.info("Debug adds {} pure clients for {}".format(debug_add, self.name))
            #     if write_to_nd and DSNBR:
            #         self.log("Debug Mode adding {} clients!".format(set_font_color(debug_add, "red")))
            #     clients += debug_add

            # Generated by upgrades:
            for u in [u for u in self._businesses if u.expects_clients]:
                temp = u.get_client_count()
                clients += temp
                min_clients += 1 # Throw in at least one min client for each business.
                if DSNBR:
                    devlog.info("{} pure clients for {}".format(temp, u.name))

            # Fame percentage mod (linear scale):
            fame_percentage = self.fame_percentage
            clients = clients/100.0*fame_percentage

            # Special check for larger buildings:
            if fame_percentage > 80 and self.maxfame > 400:
                if write_to_nd:
                    self.log("Extra clients are coming in! You business is getting very popular with the people")
                clients += float(clients)/self.maxfame*self.fame*.1

            # Upgrades:
            temp = False
            for u in self._upgrades:
                mod = getattr(u, "client_flow_mod", 0)
                if mod:
                    temp = True
                    clients = clients*mod
            if temp and write_to_nd:
                self.log("Your building upgrades are attracting extra clients!")

            # Normalize everything:
            min_clients = max(0, min_clients)
            clients = round_int(max(min_clients, clients))

            if clients and write_to_nd:
                self.log("Total of {} clients are expected to visit this establishment!".format(set_font_color(clients, "lawngreen")))

            self.total_clients = clients

        def get_max_client_capacity(self):
            """Returns the very maximum amount of clients this building can host
                at any given time. This is used in a number of ND-calculations.
            """
            capacity = 0
            for u in self._businesses:
                if u.expects_clients:
                    capacity += u.capacity
            return capacity

        @property
        def expects_clients(self):
            return any(i.expects_clients for i in self._businesses)

        def create_customer(self, name="", likes=None):
            """
            Returns a customer for this Building.
            If name is an empty string, a random customer is returned.
            If name is given, the returning customer with that name is returned
            by this method. A NameError will be raised if the given name is not
            associated with a returning customer.
            """
            if name:
                raise NotImplementedError("Returning customers are not implemented yet")

            # determine gender of random customer
            gender = choice(["male"]*5 + ['female']*2)

            # determine caste of random customer
            if self.rep < 50: caste = choice(['Peasant', 'Merchant'])
            elif 50 <= self.rep <= 150: caste = choice(['Peasant', 'Merchant', 'Nomad'])
            elif 151 <= self.rep <= 400: caste = choice(['Nomad', 'Merchant', 'Wealthy Merchant'])
            elif 401 <= self.rep <= 600: caste = choice(['Merchant', 'Wealthy Merchant', 'Clerk'])
            elif 601 <= self.rep <= 800: caste = choice(['Wealthy Merchant', 'Clerk', 'Noble'])
            else: caste = choice(['Clerk', 'Noble', 'Royal'])

            # create random customer
            min_tier = float(max(self.tier-2, .1))
            max_tier = float(self.tier + 1)
            customer = build_client(gender=gender, caste=caste,
                                    tier=uniform(min_tier, max_tier),
                                    likes=likes)
            return customer

        # SimPy/Working the building related:
        def run_nd(self):
            """This method is ran for buildings during next day
            - Gets list of workable businesses and available workers
            - Creates SimPy Environment
            """
            tl.start("{}.run_nd (SimPy/Clients, etc.)".format(self.name))
            # Setup and start the simulation
            self.flag_red = False

            if self.expects_clients:
                self.log(set_font_color("===================", "lawngreen"))
                self.log("{}".format(set_font_color("Starting the simulation:", "lawngreen")))
                self.log("--- {} ---".format(set_font_color(self.name, "lawngreen")))

                self.log("")
                if self.manager:
                    self.log("This building is managed by {} at {}% effectiveness!".format(
                                self.manager.name, self.manager_effectiveness
                    ))
                else:
                    self.log("This building has no manager assigned to it.")
                self.log("")

                # Building Stats:
                self.log("Reputation: {}%".format(self.rep_percentage))
                self.log("Fame: {}%".format(self.fame_percentage))
                self.log("Dirt: {}%".format(self.get_dirt_percentage()[0]))
                self.log("Threat: {}%".format(self.get_threat_percentage()))
                self.log("")

                self.all_workers = self.get_workers()

                # All workers and workable businesses:
                # This basically roots out Resting/None chars!
                self.available_workers = list(c for c in self.all_workers if
                                              c.action in self.jobs)
                for w in self.all_workers:
                    self.convert_AP(w)
                    # And AEQ
                    if isinstance(w.action, Job):
                        w.action.auto_equip(w)

                # Get businesses we wish SimPy to manage! business_manager method is expected here.
                self.nd_ups = list(up for up in self._businesses if up.workable)
                client_businesses = list(up for up in self._businesses if up.expects_clients)

                # Clients:
                tl.start("Generating clients in {}".format(self.name))
                self.get_client_count(write_to_nd=True)
                clnts = self.total_clients

                # TODO B&B-clients: Generate and add regulars!
                # Note (Beta): Basically what happened with this code is that all clients,
                # became regulars. For now, I'll add shuffle and regen,
                # later we want real regulars!
                if self.clients_regen_day <= day:
                    self.all_clients = set()
                    self.clients_regen_day = day + randint(2, 4)
                c0 = self.expects_clients and self.available_workers

                if c0 and len(self.all_clients) < clnts:
                    for i in xrange(clnts - len(self.all_clients)):
                        client = self.create_customer(likes=[choice(client_businesses)])
                        self.all_clients.add(client)
                self.clients = self.all_clients.copy()

                tl.end("Generating clients in {}".format(self.name))

                # Create an environment and start the setup process:
                self.env = simpy.Environment()
                for up in self._businesses:
                    up.pre_nd()

                self.env.process(self.building_manager(end=101))
                self.env.run(until=110) # 101 will run events at 100 which it is more intuitive to manage.
                self.log("{}".format(set_font_color("Ending the simulation.", "green")))

                # Building Stats:
                self.log("Reputation: {}%".format(self.rep_percentage))
                self.log("Fame: {}%".format(self.fame_percentage))
                self.log("Dirt: {}%".format(self.get_dirt_percentage()[0]))
                self.log("Threat: {}%".format(self.get_threat_percentage()))

                # We can run it for a bit more, as matrons option!?!
                # self.env.run(until=110)
                # self.log("{}".format(set_font_color("Ending the second stage of simulation:", "red")))
                income = self.fin.get_logical_income()
                if income > 0:
                    self.log("\nA total of {} Gold was earned here today!".format(set_font_color(str(income), "lawngreen")))
                elif income < 0:
                    self.log("\nA total of {} Gold was earned here today!".format(set_font_color(str(income), "red")))
                self.log("{}".format(set_font_color("===================", "lawngreen")))
                self.log("")
            else:
                self.log(set_font_color("===================", "lawngreen"))
                self.log("This is a residential building. Nothing much happened here today.")

            self.post_nd_reset()
            tl.end("{}.run_nd (SimPy/Clients, etc.)".format(self.name))

        def building_manager(self, end=100):
            """This is the main process that manages everything that is happening in the building!

            We manage workable buildings here.
            This does not benefit from being a SimPy process as it stands now.
            """
            for u in self.nd_ups:
                # Trigger all public businesses:
                if not u.active: # building is not active:
                    self.env.process(self.inactive_process())
                else: # Business as usual:
                    self.env.process(u.business_control())

                if u.has_workers():
                    u.is_running = True

            if self.expects_clients and self.total_clients:
                self.env.process(self.clients_dispatcher(end=end))

            for u in self._upgrades:
                if isinstance(u, Garden):
                    has_garden = True
                    break
            else:
                has_garden = False

            if self.manager:
                self.manager.managementskill += randint(1, 4)

            while 1:
                temp = "\n{color=[green]}%d =========>>>{/color}" % (self.env.now)
                self.log(temp)
                yield self.env.timeout(1)

                # Delete the line if nothing happened on this turn:
                if self.nd_events_report[-1] == temp:
                    del self.nd_events_report[-1]

                if not self.env.now % 25:
                    self.dirt += 5 # 5 dirt each 25 turns even if nothing is happening.
                    self.threat += self.threat_mod

                    if has_garden and dice(25):
                        for w in self.all_workers:
                            w.joy += 1

                # Clear threat and dirt for smaller buildings:
                # Maybe require any kind of manager???
                if self.capacity < 10 and not self.env.now % 100 and self.get_all_chars():
                    temp = "The building is relatively small."
                    temp += " Your employees took care of the it (Threat/Dirt cleared)!"
                    self.log(temp)
                    temp = "Don't expect this trend to continue as your business empire grows and expands!"
                    self.log(temp)
                    self.threat = 0
                    self.dirt = 0

        def clients_dispatcher(self, end=100):
            """This method provides stream of clients to the building following it's own algorithm.

            We want 50% of all clients to come in the 'rush hour' (turn 50 - 80).
            """
            expected = self.total_clients
            running = 0

            for u in self._upgrades:
                if isinstance(u, Garden):
                    has_garden = True
                    break
            else:
                has_garden = False

            # We do not want to add clients at the last 5 - 10 turns...
            # So we use 90 as base.
            normal_step = self.total_clients*.5/60
            rush_hour_step = self.total_clients*.5/30

            while expected > 0 and self.clients:
                if 50 <= self.env.now <= 80:
                    running += rush_hour_step
                else:
                    running += normal_step

                if running >= 1:
                    add_clients = round_int(running)
                    running -= add_clients

                    for i in range(add_clients):
                        expected -= 1
                        if self.clients:
                            client = self.clients.pop()
                            self.env.process(self.client_manager(client, has_garden=has_garden))

                if DSNBR:
                    devlog.info("Client Distribution running: {}".format(running))
                yield self.env.timeout(1)

        def client_manager(self, client, has_garden=False):
            """Manages a client using SimPy.

            - Picks a business
            - Tries other businesses if the original choice fails
            - Kicks the client if all fails

            So this basically sends the client into the businesses within this building or keeps them waiting/rotating.
            Once in, client is handled and managed by the Business itself until control is returned here!
            Once this method is terminated, client has completely left the building!
            """
            # Register the fact that client arrived at the building:
            temp = '{} arrives at the {}.'.format(
                        set_font_color(client.name, "beige"), self.name)
            self.log(temp, True)

            if self.dirt >= 800:
                yield self.env.timeout(1)
                temp = "Your building is as clean a pig stall. {} storms right out.".format(client.name)
                self.log(temp)
                self.env.exit()
            if self.threat >= 800:
                yield self.env.timeout(1)
                temp = "Your building is as safe as a warzone. {} ran away.".format(client.name)
                self.log(temp)
                self.env.exit()

            # Client threat mod:
            if "Aggressive" in client.traits:
                if has_garden:
                    self.threat += 2
                else:
                    self.threat += 3

            # Visit counter:
            client.up_counter("visited_building" + str(self.id))

            # Prepare data:
            businesses = [b for b in self.nd_ups if b.expects_clients]
            shuffle(businesses)

            fav_business = client.likes.intersection(self._businesses)

            # Case where clients fav business was removed from the building, client to react appropriately.
            if not fav_business:
                self.all_clients.remove(client)
                temp = "{}: {} storms out of the building pissed off as his favorite business was removed!".format(
                                        self.env.now, set_font_color(client.name, "beige"))
                self.log(temp)
                self.env.exit()
            else:
                fav_business = fav_business.pop()

            visited = 0 # Amount of businesses client has successfully visited.
            while businesses:
                # Here we pick an upgrade if a client has one in preferences:
                if not visited and fav_business in businesses:
                    # On the first run we'd want to pick the clients fav.
                    business = fav_business
                    businesses.remove(business)
                else:
                    business = businesses.pop()

                # Matron case:
                # Wait for the business to open in case of a favorite:
                if self.manager and (business == fav_business) and (business.res.count < business.capacity) and self.env.now < 85:
                    wait_till = min(self.env.now + 7, 85)
                    temp = "Your manager convinced {} to wait till {} for a slot in {} favorite {} to open up!".format(
                                    set_font_color(client.name, "beige"), wait_till, client.op, fav_business.name)
                    self.log(temp)
                    while (wait_till < self.env.now) and (business.res.count < business.capacity):
                        yield self.env.timeout(1)

                if business.type == "personal_service" and business.res.count < business.capacity:
                    # Personal Service (Brothel-like):
                    job = business.job
                    workers = business.get_workers(job, amount=1, match_to_client=client)

                    if not workers:
                        continue # Send to the next update.
                    else:
                        # We presently work just with the one char only, so:
                        worker = workers.pop()
                        if worker in self.available_workers:
                            self.available_workers.remove(worker)

                        # We bind the process to a flag and wait until it is interrupted:
                        visited += 1
                        self.env.process(business.request_resource(client, worker))
                        client.set_flag("jobs_busy")
                        while client.flag("jobs_busy"):
                            yield self.env.timeout(1)

                # Jobs like the Club:
                elif business.type == "public_service" and business.res.count < business.capacity:
                    self.env.process(business.client_control(client))
                    visited += 1
                    client.set_flag("jobs_busy")
                    while client.flag("jobs_busy"):
                        yield self.env.timeout(1)

            if not visited:
                temp = "There is not much for the {} to do...".format(set_font_color(client.name, "beige"))
                self.log(temp)
                temp = "So {} leaves your establishment cursing...".format(set_font_color(client.name, "beige"))
                self.log(temp)
                self.env.exit()
            else:
                temp = '{} is leaving after visiting {} business(es).'.format(set_font_color(client.name, "beige"), visited)
                self.log(temp)

        def post_nd_reset(self):
            self.env = None
            self.nd_ups = list()

            for _ in self._businesses:
                _.post_nd_reset()

            for c in self.all_clients:
                for f in c.flags.keys():
                    if f.startswith("jobs"):
                        c.del_flag(f)

        def convert_AP(self, worker):
            # Do not convert AP when Char is in school.
            if getattr(worker.location, "is_school", False):
                return
            worker.jobpoints = worker.AP*100
            worker.AP = 0
