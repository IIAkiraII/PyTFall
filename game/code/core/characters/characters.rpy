# Characters classes and methods:
init -9 python:
    ###### Character Helpers ######
    class Tier(_object):
        """This deals with expectations and social status of chars.

        Used to calculate expected wages, upkeep, living conditions and etc.
        I'd love it to contain at least some of the calculations and conditioning for Jobs as well, we can split this if it gets too confusing.
        Maybe some behavior flags and alike can be a part of this as well?
        """
        BASE_WAGES = {"SIW": 20, "Warrior": 30, "Server": 15, "Specialist": 25}

        def __init__(self):
            # self.instance = instance

            self.tier = 0

            self.expected_wage = 0
            self.paid_wage = 0
            self.upkeep = 0
            self.expected_accomodations = "poor"

        def get_max_skill(self, skill, tier=None):
            if tier is None:
                tier = self.tier or 1
            return SKILLS_MAX[skill]*(tier*.1)

        def recalculate_tier(self):
            """
            I think we should attempt to figure out the tier based on
            level and stats/skills of basetraits.

            level always counts as half of the whole requirement.
            stats and skills make up the other half.

            We will aim at specific values and interpolate.
            In case of one basetrait, we multiply result by 2!
            """
            target_tier = self.tier+1.0 # To get a float for Py2.7
            target_level = (target_tier)*20
            tier_points = 0 # We need 100 to tier up!

            level_points = self.level*50.0/target_level

            default_points = 12.5
            skill_bonus = 0
            stat_bonus = 0
            for trait in self.traits.basetraits:
                # Skills first (We calc this as 12.5% of the total)
                skills = trait.base_skills
                if not skills: # Some weird ass base trait, we just award 33% of total possible points.
                    skill_bonus += default_points*.33
                else:
                    total_weight_points = sum(skills.values())
                    for skill, weight in skills.items():
                        weight_ratio = float(weight)/total_weight_points
                        max_p = default_points*weight_ratio

                        sp = self.get_skill(skill)
                        sp_required = self.get_max_skill(skill, target_tier)

                        skill_bonus += min(sp*max_p/sp_required, max_p*1.1)

                stats = trait.base_stats
                if not stats: # Some weird ass base trait, we just award 33% of total possible points.
                    stat_bonus += default_points*.33
                else:
                    stats = trait.base_stats
                    for stat, weight in stats.items():
                        weight_ratio = float(weight)/total_weight_points
                        max_p = default_points*weight_ratio

                        sp = self.stats.stats[stat]
                        sp_required = self.get_max(stat)

                        stat_bonus += min(sp*max_p/sp_required, max_p*1.1)

            stats_skills_points = skill_bonus + stat_bonus
            if len(self.traits.basetraits) == 1:
                stats_skills_points *= 2

            total_points = level_points + stats_skills_points

            # devlog.info("Name: {}, total tier points for Teir {}: {} (lvl: {}, st/sk=total: {}/{}==>{})".format(self.name,
            #                                                                                             int(target_tier),
            #                                                                                             round(total_points),
            #                                                                                             round(level_points),
            #                                                                                             round(stat_bonus),
            #                                                                                             round(skill_bonus),
            #                                                                                             round(stats_skills_points)))

            if total_points >= 100:
                self.tier += 1 # we tier up and return True!
                return True
            else:
                return False

        def calc_expected_wage(self, kind=None):
            """Amount of money each character expects to get paid for her skillset.

            Keeping it simple for now:
            - We'll set defaults for all basic occupation types.
            - We'll adjust by tiers.
            - We'll adjust by other modifiers like traits.

            kind: for now, any specific general occupation will do, but
            we may use jobs in the future somehow. We provide this when hiring
            for a specific task. If None, first occupation found when iterating
            default list will do...
            """
            if kind:
                wage = self.BASE_WAGES[kind]
            else:
                for i in ["Warrior", "Specialist", "SIW", "Server"]:
                    if i in self.occupations:
                        wage = self.BASE_WAGES[i]
                        break
                else:
                    raise Exception("Impossible character detected! ID: {} ~ BT: {} ~ Occupations: {}".format(self.id,
                                    ", ".join([str(t) for t in self.traits.basetraits]), ", ".join([str(t) for t in self.occupations])))

            # Each tier increases wage by 50% without stacking:
            wage = wage + wage*self.tier*.5

            if "Dedicated" in self.traits:
                wage = wage*.75

            # Normalize:
            wage = int(round(wage))
            if wage < 10:
                wage = 10

            self.expected_wage = wage
            return wage

        def update_tier_info(self, kind=None):
            for i in range(11):
                if not self.recalculate_tier():
                    break
            self.calc_expected_wage(kind=kind)

        # We need "reverse" calculation for when leveling up characters
        # Mainly to figure out their skill levels, maybe moar in the future
        def level_up_tier_to(self, level):
            level_mod = level*.5 # We take level 200 as max...

            skills = {}
            # First, we get highest skill relevance from basetraits:
            for bt in self.traits.basetraits:
                for skill, value in bt.base_skills.items():
                    skills[skill] = max(skills.get(skill, 0), value)

            # Bit of an issue here is that we do not mind threathholds, not sure that it's a good thing.
            for skill, value in skills.items():
                value = (MAX_SKILLS[skill]*.01*value)*(.01*level_mod)
                self.stats.mod_full_skill(skill, value)


    class Team(_object):
        def __init__(self, name="", implicit=None, free=False, max_size=3):
            if not implicit:
                implicit = list()
            self.name = name
            self.implicit = implicit
            self.max_size = max_size
            self._members = list()
            self._leader = None
            self.free = free # Free teams do not have any implicit members.

            # BE Assests:
            self.position = None # BE will set it to "r" or "l" short for left/right on the screen.

            if self.implicit:
                for member in self.implicit:
                    self.add(member)

        def __len__(self):
            return len(self._members)

        def __iter__(self):
            return iter(self._members)

        def __getitem__(self, index):
            return self._members[index]

        def __nonzero__(self):
            return bool(self._members)

        @property
        def members(self):
            return self._members

        @property
        def leader(self):
            try:
                return self.members[0]
            except:
                return self._leader

        def add(self, member):
            if member in self:
                notify("Impossible to join the same team twice")

            if len(self._members) >= self.max_size:
                temp = []
                t = "{} team cannot have more than {} team members!".format(self.name, self.max_size)
                temp.append(t)
                t = [m.name for m in self._members]
                temp.append("Members: {}".format(", ".join(t)))
                t = "Adding: {}".format(member.name)
                temp.append(t)
                temp = "\n".join(temp)
                raise Exception(temp)
                notify(temp)
            else:
                if not self.free and not self.leader:
                    self._leader = member
                    if member not in self.implicit:
                        self.implicit.append(member)
                    self._members.append(member)
                else:
                    self._members.append(member)

        def remove(self, member):
            if member in self.implicit or member not in self._members:
                notify("%s is not a member of this team or an implicit member of this team!"%member.name)
            else:
                self._members.remove(member)

        def set_leader(self, member):
            if member not in self._members:
                notify("%s is not a member of this team!"%member.name)
                return
            if self.leader:
                self.implicit.remove(self.leader)
            self._leader = member
            self.implicit.insert(0, member)

        def get_level(self):
            """
            Returns an average level of the team as an integer.
            """
            av_level = 0
            for member in self._members:
                av_level += member.level
            return int(math.ceil(av_level/len(self._members)))

        def get_rep(self):
            """
            Returns average of arena reputation of a team as an interger.
            """
            arena_rep = 0
            for member in self._members:
                arena_rep += member.arena_rep
            return int(math.ceil(arena_rep/len(self._members)))

        # BE Related:
        def reset_controller(self):
            # Resets combat controller
            for m in self.members:
                m.controller = "player"


    class JobsLogger(_object):
        # Used to log stats and skills during job actions
        def __init__(self):
            self.stats_skills = dict()

        def logws(self, s, value):
            """Logs workers stat/skill to a dict:
            """
            self.stats_skills[s] = self.stats_skills.get(s, 0) + value

        def clear_jobs_log(self):
            self.stats_skills = dict()


    class SmartTracker(collections.MutableSequence):
        def __init__(self, instance, be_skill=True):
            self.instance = instance # Owner of this object, this is being instantiated as character.magic_skills = SmartTracker(character)
            self.normal = set() # Normal we consider anything that's been applied by normal game operations like events, loading routines and etc.
            self.items = dict() # Stuff that's been applied through items, it's a counter as multiple items can apply the same thing (like a trait).
            self.be_skill = be_skill # If we expect a be skill or similar mode.
            self.list = _list()

        def __len__(self): return len(self.list)

        def __getitem__(self, i): return self.list[i]

        def __delitem__(self, i): del self.list[i]

        def __setitem__(self, i, v):
            self.list[i] = v

        def insert(self, i, v):
            self.list.insert(i, v)

        def __str__(self):
            return str(self.list)

        def append(self, item, normal=True):
            # Overwriting default list method, always assumed normal game operations and never adding through items.
            # ==> For battle & magic skills:
            if self.be_skill:
                if isinstance(item, basestring):
                    if item in store.battle_skills:
                        item = store.battle_skills[item]
                    else:
                        devlog.warning("Tried to apply unknown skill %s to %s!" % (item, self.instance.__class__))
                        return
            if normal: #  Item applied by anything other than that
                self.normal.add(item)
            else:
                self.items[item] = self.items.get(item, 0) + 1

            # The above is enough for magic/battle skills, but for traits... we need to know if the effects should be applied.
            if item in self.normal or self.items.get(item, 0) > 0:
                if not item in self.list:
                    self.list.append(item)
                    return True

        def remove(self, item, normal=True):
            # Overwriting default list method.
            # ==> For battle & magic skills:
            if self.be_skill:
                if isinstance(item, basestring):
                    if item in store.battle_skills:
                        item = store.battle_skills[item]
                    else:
                        devlog.warning("Tried to remove unknown skill %s from %s!" % (item, self.instance.__class__))
                        return
            if normal:
                if item in self.normal:
                    self.normal.remove(item)
            else:
                self.items[item] = self.items.get(item, 0) - 1

            # The above is enough for magic/battle skills, but for traits... we need to know if the effects should be applied.
            if not item in self.normal and self.items.get(item, 0) <= 0:
                if item in self.list:
                    self.list.remove(item)
                    return True


    class Trait(_object):
        def __init__(self):
            self.desc = ''
            self.icon = None
            self.hidden = False
            self.mod = dict() # To be removed!
            self.mod_stats = dict()
            self.mod_skills = dict()
            self.max = dict()
            self.min = dict()
            self.blocks = list()
            self.effects = list()

            # Occupations related:
            self.occupations = list() # GEN_OCCS (Misnamed here)
            self.higher_tiers = list() # Required higher tier basetraits to enable this trait.

            self.sex = "unisex" # Untill we set this up in traits: this should be "unisex" by default.

            # Types:
            self.type = "" # Specific type if specified.
            self.basetrait = False
            self.personality = False
            self.race = False
            self.breasts = False
            self.body = False
            self.elemental = False

            self.mod_ap = 0 # Will only work on body traits!

            self.mob_only = False
            self.character_trait = False
            self.sexual = False
            self.client = False
            self.market = False

            # Elemental:
            self.font_color = None
            self.resist = list()
            self.el_name = ""
            self.el_absorbs = dict() # Pure ratio, NOT a modificator to a multiplier like for dicts below.
            self.el_damage = dict()
            self.el_defence = dict()
            self.el_special = dict()

            # Base mods on init:
            self.init_mod = dict() # Mod value setting
            self.init_lvlmax = dict() # Mod value setting
            self.init_max = dict() # Mod value setting
            self.init_skills = dict() # {skill: [actions, training]}

            # Special BE Fields:
            # self.evasion_bonus = () # Bonuses in traits work differently from item bonuses, a tuple of (min_value, max_value, max_value_level) is expected (as a value in dict below) instead!
            # self.ch_multiplier = 0 # Critical hit multi...
            # self.damage_multiplier = 0

            # self.defence_bonus = {} # Delivery! Not damage types!
            # self.defence_multiplier = {}
            # self.delivery_bonus = {} Expects a k/v pair of type: multiplier This is direct bonus added to attack power.
            # self.delivery_multiplier = {}

            self.leveling_stats = dict() # {stat: [lvl_max, max **as mod values]}

            # For BasetTraits, we want to have a list of skills and stats, possibly weighted for evaluation.
            self.base_skills = dict()
            self.base_stats = dict()
            # Where key: value are stat/skill: weight!

        def __str__(self):
            return str(self.id)


    class Traits(SmartTracker):
        def __init__(self, *args, **kwargs):
            """
            Trait effects are being applied per level on activation of a trait and on level-ups.
            """
            # raise Exception(args[0])
            # SmartTracker.__init__(self, args[0])
            super(Traits, self).__init__(args[0])
            # self.instance = args[0]

            self.ab_traits = set()  # Permenatly blocked traits (Absolute Block Traits)
            self.blocked_traits = set()  # Blocked traits

            self.basetraits = set() # A set with basetraits (2 maximum)

        def __getattr__(self, item):
            raise AttributeError("%s object has no attribute named %r" %
                                 (self.__class__.__name__, item))

        def __contains__(self, item):
            if isinstance(item, basestring):
                if item in store.traits: item = store.traits[item]
                else: return False

            return super(Traits, self).__contains__(item)

        @property
        def gen_occs(self):
            # returns a list of general occupation from Base Traits only.
            gen_occs = list()
            for go in chain.from_iterable(t.occupations for t in self.basetraits):
                if go not in gen_occs:
                    gen_occs.append(go)
            return gen_occs

        @property
        def base_to_string(self):
            return ", ".join(sorted(list(str(t) for t in self.basetraits)))

        def apply(self, trait, truetrait=True):
            """
            Activates trait and applies it's effects all the way up to a current level of the characters.
            Truetraits basially means that the trait is not applied throught items (Jobs, GameStart, Events and etc.)
            """
            # If we got a string with a traits name. Let the game throw an error otherwise.
            if not isinstance(trait, Trait):
                trait = store.traits[trait]
            char = self.instance

            # All the checks required to make sure we can even apply this fucking trait: ======================>>
            if trait.sex not in ["unisex", char.gender]:
                return

            # We cannot allow "Neutral" element to be applied if there is at least one element present already:
            if trait.elemental and trait.id == "Neutral":
                if self.instance.elements:
                    return

            # Blocked traits:
            if trait in self.ab_traits | self.blocked_traits:
                return

            # Unique Traits:
            if trait.personality and list(t for t in self if t.personality):
                return
            if trait.race and list(t for t in self if t.race):
                return
            if trait.breasts and list(t for t in self if t.breasts):
                return
            if trait.body and list(t for t in self if t.body):
                return
            if trait.personality:
                char.personality = trait
            if trait.race:
                char.race = trait
            if trait.breasts:
                char.breasts = trait
            if trait.body:
                char.body = trait

            # We need to make sure that no more than x + len(basetraits) of basetraits can be applied, atm x is 4:
            if trait.basetrait:
                if trait not in self.basetraits:
                    if trait.higher_tiers and list(traits[t] for t in trait.higher_tiers if t in self.basetraits):
                        allowed = 4 + len(self.basetraits)
                        bt = len(list(t for t in self if t.basetrait))
                        if bt == allowed:
                            return
                        elif bt > allowed:
                            devlog.warning("BASE TRAITS OVER THE ALLOWED MAX! CHECK Traits.apply method!")
                            return

            if not super(Traits, self).append(trait, truetrait):
                return

            # If we got here... we can apply the effect? Maybe? Please? Just maybe? I am seriouslly pissed at this system right now... ===========>>>

            stats = self.instance.stats
            # If the trait is a basetrait:
            if trait in self.basetraits:
                multiplier = 2 if len(self.basetraits) == 1 else 1
                for stat in trait.init_lvlmax: # Mod value setting
                    if stat in stats:
                        stats.lvl_max[stat] += trait.init_lvlmax[stat] * multiplier
                    else:
                        msg = "'%s' trait tried to apply unknown init lvl max stat: %s!"
                        devlog.warning(str(msg % (trait.id, stat)))

                for stat in trait.init_max: # Mod value setting
                    if stat in stats:
                        stats.max[stat] += trait.init_max[stat] * multiplier
                    else:
                        msg = "'%s' trait tried to apply unknown init max stat: %s!"
                        devlog.warning(str(msg % (trait.id, stat)))

                for stat in trait.init_mod: # Mod value setting
                    if stat in stats:
                        stats.stats[stat] += trait.init_mod[stat] * multiplier
                    else:
                        msg = "'%s' trait tried to apply unknown init max stat: %s!"
                        devlog.warning(str(msg % (trait.id, stat)))

                for skill in trait.init_skills: # Mod value setting
                    if skill in stats.skills:
                        stats.skills[skill][0] += trait.init_skills[skill][0] * multiplier
                        stats.skills[skill][1] += trait.init_skills[skill][1] * multiplier
                    else:
                        msg = "'%s' trait tried to apply unknown init skillt: %s!"
                        devlog.warning(str(msg % (trait.id, skill)))

            # Only for body traits:
            if trait.body:
                if trait.mod_ap:
                    self.instance.baseAP += trait.mod_ap

            for key in trait.max:
                if key in stats.max:
                   stats.max[key] += trait.max[key]
                else:
                    msg = "'%s' trait tried to apply unknown max stat: %s!"
                    devlog.warning(str(msg % (trait.id, key)))

            for key in trait.min:
                # Preventing traits from messing up minimums of stats by pushing them into negative territory. @Review: No longer required as per new stats code.
                if key in stats.min:
                    stats.min[key] += trait.min[key]
                else:
                    msg = "'%s' trait tried to apply unknown min stat: %s!"
                    devlog.warning(str(msg % (trait.id, key)))

            for entry in trait.blocks:
                if entry in traits:
                    self.blocked_traits.add(traits[entry])
                else:
                    devlog.warning(str("Tried to block unknown trait: %s, id: %s, class: %s" % (entry, char.id, char.__class__)))

            # For now just the girls get effects...
            if hasattr(char, "effects"):
                for entry in trait.effects:
                    char.enable_effect(entry)

            if trait.mod_stats:
                if hasattr(char, "upkeep"):
                    char.upkeep += trait.mod_stats.get("upkeep", [0, 0])[0]
                if hasattr(char, "disposition"):
                    char.disposition += trait.mod_stats.get("disposition", [0, 0])[0]
                for level in xrange(char.level+1):
                    char.stats.apply_trait_statsmod(trait)

            if hasattr(trait, "mod_skills"):
                for key in trait.mod_skills:
                    if key in char.SKILLS:
                        sm = stats.skills_multipliers[key] # skillz muplties
                        m = trait.mod_skills[key] # mod
                        sm[0] += m[0]
                        sm[1] += m[1]
                        sm[2] += m[2]
                    else:
                        msg = "'%s' trait tried to apply unknown skill: %s!"
                        devlog.warning(str(msg % (trait.id, key)))

            # Adding resisting elements and attacks:
            for i in trait.resist:
                self.instance.resist.append(i)

            # NEVER ALLOW NEUTRAL ELEMENT WITH ANOTHER ELEMENT!
            if trait.elemental:
                if trait.id != "Neutral" and traits["Neutral"] in self:
                    self.remove(traits["Neutral"])

            # Finally, make sure stats are working:
            char.stats.normalize_stats()

        def remove(self, trait, truetrait=True):
            """
            Removes trait and removes it's effects gained up to a current level of the characters.
            Truetraits basially means that the trait is not applied throught items (Jobs, GameStart, Events and etc.)
            """
            # If we got a string with a traits name. Let the game throw an error otherwise.
            if not isinstance(trait, Trait):
                trait = store.traits[trait]
            char = self.instance

            if trait.sex not in ["unisex", char.gender]:
                return

            # We Never want to remove a base trait:
            if trait in self.basetraits:
                return

            # WE NEVER REMOVE PERMANENT TRAITS FAMILY:
            if any([trait.personality, trait.race, trait.breasts, trait.body]):
                return

            if not super(Traits, self).remove(trait, truetrait):
                return

            stats = char.stats
            for key in trait.max:
                if key in stats.max:
                    stats.max[key] -= trait.max[key]
                else:
                    devlog.warning(str('Maximum Value: %s for Trait: %s does not exist' % (key, trait.id)))

            for key in trait.min:
                if key in stats.min:
                    # Preventing traits from messing up minimums of stats by pushing them into negative territory. @Review: No longer required as per new stats code.
                    # if(self.stats.min[key] - trait.min[key]) >= 0:
                    stats.min[key] -= trait.min[key]
                else:
                    msg = "'%s' trait tried to apply unknown min stat: %s!"
                    devlog.warning(str(msg % (trait.id, key)))

            if trait.blocks:
                _traits = set()
                for entry in trait.blocks:
                    if entry in traits:
                        _traits.add(traits[entry])
                    else:
                        devlog.warning(str("Tried to block unknown trait: %s, id: %s, class: %s" % (entry, char.id, char.__class__)))
                self.blocked_traits -= _traits

            # Ensure that blocks forced by other traits were not removed:
            for entry in self:
                self.blocked_traits = self.blocked_traits.union(entry.blocks)

            # For now just the girls get effects...
            if isinstance(char, Char):
                for entry in trait.effects:
                    self.instance.disable_effect(entry)

            if trait.mod_stats:
                if hasattr(char, "upkeep"):
                    char.upkeep -= trait.mod_stats.get("upkeep", [0, 0])[0]
                if hasattr(char, "disposition"):
                    char.disposition -= trait.mod_stats.get("disposition", [0, 0])[0]
                for level in xrange(char.level+1):
                    char.stats.apply_trait_statsmod(trait, reverse=True)

            if hasattr(trait, "mod_skills"):
                for key in trait.mod_skills:
                    if key in char.SKILLS:
                        sm = stats.skills_multipliers[key] # skillz muplties
                        m = trait.mod_skills[key] # mod
                        sm[0] -= m[0]
                        sm[1] -= m[1]
                        sm[2] -= m[2]
                    else:
                        msg = "'%s' trait tried to apply unknown skill: %s!"
                        devlog.warning(str(msg % (trait.id, key)))

            # Remove resisting elements and attacks:
            for i in trait.resist:
                self.instance.resist.remove(i)

            # We add the Neutral element if there are no elements left at all...
            if not self.instance.elements:
                self.apply("Neutral")

            # Finally, make sure stats are working:
            char.stats.normalize_stats()


    class Finances(_object):
        """Helper class that handles finance related matters in order to reduce
        the size of Characters/Buildings classes."""
        def __init__(self, *args, **kwargs):
            """Main logs log actual finances (money moving around)
            Jobs income logs don't do any such thing. They just hold info about
            how much building or character earned for MC or how much MC payed
            to them
            """
            self.instance = args[0]
            self.todays_main_income_log = dict()
            self.todays_main_expense_log = dict()
            self.todays_logical_income_log = dict()
            self.todays_logical_expense_log = dict()

            self.game_main_income_log = dict()
            self.game_main_expense_log = dict()
            self.game_logical_income_log = dict()
            self.game_logical_expense_log = dict()

            self.income_tax_debt = 0
            self.property_tax_debt = 0

        # Logging actual data (money moving around)
        def log_income(self, value, kind):
            """Logs private Income."""
            value = int(round(value))
            temp = self.todays_main_income_log
            temp[kind] = temp.get(kind, 0) + value

        def log_expense(self, value, kind):
            """Logs private expence."""
            value = int(round(value))
            temp = self.todays_main_expense_log
            temp[kind] = temp.get(kind, 0) + value

        # Logging logical data (just for info)
        def log_logical_income(self, value, kind):
            """Logs Jobs income (logical) (Buildings or Chars)"""
            value = int(round(value))
            temp = self.todays_logical_income_log
            temp[kind] = temp.get(kind, 0) + value

        def log_logical_expense(self, value, kind):
            """Logs Jobs expense (logical) (Buildings or Chars)"""
            value = int(round(value))
            temp = self.todays_logical_expense_log
            temp[kind] = temp.get(kind, 0) + value

        def add_money(self, value, reason="Other"):
            value = int(round(value))
            self.log_income(value, reason)
            self.instance.gold += value

        def take_money(self, value, reason="Other"):
            value = int(round(value))
            if value <= self.instance.gold:
                self.log_expense(value, reason)
                self.instance.gold -= value
                return True
            return False

        # Retrieving data:
        def get_data_for_fin_screen(self, type=None):
            if type == "logical":
                all_income_data = self.game_logical_income_log.copy()
                all_income_data[store.day] = self.todays_logical_income_log

                all_expense_data = self.game_logical_expense_log.copy()
                all_expense_data[store.day] = self.todays_logical_expense_log
            if type == "main":
                all_income_data = self.game_main_income_log.copy()
                all_income_data[store.day] = self.todays_main_income_log

                all_expense_data = self.game_main_expense_log.copy()
                all_expense_data[store.day] = self.todays_main_expense_log

            days = []
            for d in all_income_data:
                if all_income_data[d] or all_expense_data[d]:
                    days.append(d)
            days = days[-7:]
            if days and len(days) > 1:
                days.append("All")
                all_income_data["All"] = add_dicts(all_income_data.values())
                all_expense_data["All"] = add_dicts(all_expense_data.values())
            return days, all_income_data, all_expense_data

        def get_logical_income(self, kind="all", day=None):
            """Retrieve work income (for buildings/chars?)

            kind = "all" means any income earned on the day.
            """
            if day and day >= store.day:
                raise Exception("Day on income retrieval must be lower than the current day!")

            if not day:
                d = self.todays_logical_income_log
            else:
                d = self.game_logical_income_log[day]

            if kind == "all":
                return sum(val for val in d.values())
            elif kind in d:
                return d[kind]
            else:
                raise Exception("Income kind: {} is not valid!".format(kind))

        def get_total_taxes(self, days):
            # char = self.instance
            # income = dict()
            # businesses = [b for b in char.buildings if hasattr(b, "fin")]
            # for b in businesses:
            #     for _day in b.fin.game_fin_log:
            #         if int(_day) > day - days:
            #             for key in b.fin.game_fin_log[_day][0]["private"]:
            #                 income[key] = income.get(key, 0) + b.fin.game_fin_log[_day][0]["private"][key]
            #             for key in b.fin.game_fin_log[_day][0]["work"]:
            #                 income[key] = income.get(key, 0) + b.fin.game_fin_log[_day][0]["work"][key]
            #
            # income = sum(income.values())
            #
            # if income <= 5000:
            #     tax = 0
            # elif income <= 25000:
            #     tax = int(round(income*0.1))
            # elif income <= 50000:
            #     tax = int(round(income*0.2))
            # elif income <= 100000:
            #     tax = int(round(income*0.3))
            # elif income <= 200000:
            #     tax = int(round(income*0.4))
            # else:
            #     tax = int(round(income*0.45))
            #
            # for b in businesses:
            #     tax += int(b.price*0.04)
            # for ch in char.chars:
            #     if ch.status == "slave":
            #         tax += int(ch.fin.get_price()*0.05)
            tax = 100
            return tax
        # ================================>
        # Rest

        def settle_wage(self, txt, img):
            """
            Settle wages between player and chars.
            Called during next day method per each individual girl.
            """
            char = self.instance
            got_paid = False

            # total_wage = sum(self.todays_logical_income_log.values())
            # hero.add_money(total_wage, reason="Businesses")
            txt.append("\n")

            wage = round_int(char.expected_wage/100.0*char.wagemod)
            if wage and hero.take_money(wage, reason="Wages"):
                self.add_money(wage, reason="Wages")
                self.log_logical_expense(wage, "Wages") # Is this correct?
                if isinstance(char.workplace, Building):
                    char.workplace.fin.log_logical_expense(wage, "Wages")
                if config.debug:
                    txt.append("DEBUG: You paid {} in wages!\n".format(wage))
                got_paid = True

            if char.status != "slave":
                diff = char.wagemod-100
                dismod = .09
                joymod = .06
            else:
                diff = char.wagemod
                dismod = .1
                joymod = .1

            if wage and not got_paid:
                temp = "You failed to pay her promised wage..."
                txt.append(temp)
            else:
                if char.status != "slave":
                    temp = choice(["She expects to be compensated for her services ( %d Gold). " % char.expected_wage,
                                   "She expects to be paid a wage of %d Gold. " % char.expected_wage])
                else:
                    temp = choice(["Being a slave, she doesn't expect to get paid. ",
                                   "Slaves don't get paid. "])
                txt.append(temp)

                if diff == 0:
                    temp = "And she got exactly that in wages! "
                    img = "profile"
                elif diff > 0:
                    temp = choice(["You've paid her {}% more than that! ".format(diff),
                                   "She got {}% more for her services. ".format(diff)])
                    img = char.show("profile", "happy", resize=(500, 600))
                elif diff < 0:
                    temp = choice(["She has received {}% less... You should really pay your girls a fair wage if you expect them to be happy and loyal.".format(diff),
                                   "She got {}% less than that! ".format(diff)])
                    img = char.show("profile", "angry", resize=(500, 600))
                    dismod = -dismod
                    joymod = -joymod
                char.disposition += round_int(diff*dismod)
                char.joy += round_int(diff*joymod)
                txt.append(temp)
                txt.append("\n")

            return img

        def get_price(self):
            char = self.instance

            price = 1000 + char.tier*1000 + char.level*100

            if char.status == 'free':
                price *= 2 # in case if we'll even need that for free ones, 2 times more

            return price

        def get_upkeep(self):
            char = self.instance

            if char.status == 'slave':
                if hasattr(char, "upkeep"):
                    upkeep = char.upkeep
                else:
                    upkeep = 0

                upkeep *= char.tier+1

                if "Dedicated" in char.traits:
                    upkeep += 25 + char.tier*100 + char.level*2
                else:
                    upkeep += 50 + char.tier*100 + char.level*5

                return max(20, upkeep)
            else:
                return 0

        def next_day(self):
            self.game_main_income_log[day] = self.todays_main_income_log.copy()
            self.game_main_expense_log[day] = self.todays_main_expense_log.copy()
            self.game_logical_income_log[day] = self.todays_logical_income_log.copy()
            self.game_logical_expense_log[day] = self.todays_logical_expense_log.copy()

            self.todays_main_income_log = dict()
            self.todays_main_expense_log = dict()
            self.todays_logical_income_log = dict()
            self.todays_logical_expense_log = dict()


    class Stats(_object):
        """Holds and manages stats for PytCharacter Classes.
        DEVNOTE: Be VERY careful when accesing this class directly!
        Some of it's methods assume input from self.instance__setattr__ and do extra calculations!
        """
        FIXED_MAX = set(['joy', 'mood', 'disposition', 'vitality', 'luck', 'alignment'])
        def __init__(self, *args, **kwargs):
            """
            instance = reference to Character object
            Expects a dict with statname as key and a list of:
            [stat, min, max, lvl_max] as value.
            Added skills to this class... (Maybe move to a separate class if they get complex?).
            DevNote: Training skills have a capital letter in them, action skills do not. This should be done thought the class of the character and NEVER using self.mod_skill directly!
            """
            self.instance = args[0]
            self.stats, self.imod, self.min, self.max, self.lvl_max = dict(), dict(), dict(), dict(), dict()

            # Load the stat values:
            for stat, values in kwargs.get("stats", {}).iteritems():
                self.stats[stat] = values[0]
                self.imod[stat] = 0
                self.min[stat] = values[1]
                self.max[stat] = values[2]
                self.lvl_max[stat] = values[3]

            # [action_value, training_value]
            self.skills = {k: [0, 0] for k in self.instance.SKILLS}
            # [actions_multi, training_multi, value_multi]
            self.skills_multipliers = {k: [1, 1, 1] for k in self.skills}

            # Leveling system assets:
            self.goal = 1000
            self.goal_increase = 1000
            self.level = 1
            self.exp = 0

            # Statslog:
            self.log = dict()

        def _raw_skill(self, key):
            """Raw Skills:
            [action_value, training_value]
            """
            if key.islower(): return self.skills[key][0]
            else: return self.skills[key.lower()][1]

        def _get_stat(self, key):
            maxval = self.get_max(key)
            minval = self.min[key]
            val = self.stats[key] + self.imod[key]

            # Normalization:
            if val > maxval:
                if self.stats[key] > maxval:
                    self.stats[key] = maxval
                val = maxval

            elif val < minval:
                if self.stats[key] < minval:
                    self.stats[key] = minval
                val = minval

            if key not in ["disposition", "luck"] and val < 0:
                val = 0

            return val

        def get_skill(self, skill):
            """
            Returns adjusted skill.
            'Action' skill points become less useful as they exceed training points * 3.
            """
            skill = skill.lower()
            action = self._raw_skill(skill)
            training = self._raw_skill(skill.capitalize())

            training_range = training * 3
            beyond_training = action - training_range

            if beyond_training >= 0:
                training += training_range + beyond_training / 3.0
            else:
                training += action
            return training * max(min(self.skills_multipliers[skill][2], 1.5), 0.5)

        def is_skill(self, key):
            # Easy check for skills.
            return key.lower() in self.skills

        def is_stat(self, key):
            # Easy check for stats.
            return key.lower() in self.stats

        def normalize_stats(self, stats=None):
            # Makes sure main stats dict is properly aligned to max/min values

            if not stats:
                stats = self.stats

            for stat in stats:
                val = self.stats[stat]
                minval = self.min[stat]
                maxval = self.get_max(stat)
                if val > maxval:
                    self.stats[stat] = maxval
                if val < minval:
                    self.stats[stat] = minval

        def __getitem__(self, key):
            return self._get_stat(key)

        def __iter__(self):
            return iter(self.stats)

        def get_max(self, key):
            val = min(self.max[key], self.lvl_max[key])
            if key not in ["disposition"]:
                if val < 0:
                    val = 0
            return val

        def mod_item_stat(self, key, value):
            if key in self.stats:
                self.imod[key] = self.imod[key] + value

        def settle_effects(self, key, value):
            if hasattr(self.instance, "effects"):
                effects = self.instance.effects

                if key == 'disposition':
                    if effects['Insecure']['active']:
                        if value >= 5:
                            self.instance.joy += 1
                        elif value <= -5:
                            self.instance.joy -= 1
                    if effects['Introvert']['active']:
                        value = int(value*.8)
                    elif effects['Extrovert']['active']:
                        value = int(value*1.2)
                    if effects['Loyal']['active'] and value < 0: # works together with other traits
                        value = int(value*.8)

                    if last_label.startswith("interactions_"):
                        tag = str(random.random())
                        renpy.show_screen("display_disposition", tag, value, 40, 530, 400, 1)
                elif key == 'joy':
                    if effects['Impressible']['active']:
                        value = int(value*1.5)
                    elif effects['Calm']['active']:
                        value = int(value*0.5)
            return value

        def _mod_exp(self, value):
            # Assumes input from setattr of self.instance:
            if hasattr(self.instance, "effects"):
                effects = self.instance.effects
                if effects["Slow Learner"]["active"]:
                    val = value - self.exp
                    value = self.exp + int(round(val*.9))
                if effects["Fast Learner"]["active"]:
                    val = value - self.exp
                    value = self.exp + int(round(val*1.1))

            self.exp = value

            while self.exp >= self.goal:
                self.goal_increase += 1000
                self.goal += self.goal_increase
                self.level += 1

                # Bonuses from traits:
                for trait in self.instance.traits:
                    self.apply_trait_statsmod(trait)

                # Normal Max stat Bonuses:
                for stat in self.stats:
                    if stat not in self.FIXED_MAX:
                        self.lvl_max[stat] += 5
                        self.max[stat] += 2

                        # Chance to increase max stats permanently based on level
                        if self.level >= 20:
                            val = self.level / 20.0
                            if dice(val):
                                self.lvl_max[stat] +=1
                            if dice(val):
                                self.max[stat] +=1

                # Super Bonuses from Base Traits:
                if hasattr(self.instance, "traits"):
                    traits = self.instance.traits.basetraits
                    multiplier = 2 if len(traits) == 1 else 1
                    for trait in traits:
                        # Super Stat Bonuses:
                        for stat in trait.leveling_stats:
                            if stat not in self.FIXED_MAX and stat in self.stats:
                                self.lvl_max[stat] += trait.leveling_stats[stat][0] * multiplier
                                self.max[stat] += trait.leveling_stats[stat][1] * multiplier
                            else:
                                msg = "'%s' stat applied on leveling up (max mods) to %s (%s)!"
                                devlog.warning(str(msg % (stat, self.instance.__class__, trait.id)))

                        # Super Skill Bonuses:
                        for skill in trait.init_skills:
                            if self.is_skill(skill):
                                ac_val = round(trait.init_skills[skill][0] * 0.02) + self.level / 5
                                tr_val = round(trait.init_skills[skill][1] * 0.08) + self.level / 2
                                self.skills[skill][0] = self.skills[skill][0] + ac_val
                                self.skills[skill][1] = self.skills[skill][1] + tr_val
                            else:
                                msg = "'{}' skill applied on leveling up to {} ({})!"
                                devlog.warning(str(msg.format(stat, self.instance.__class__, trait.id)))

                self.stats["health"] = self.get_max("health")
                self.stats["mp"] = self.get_max("mp")
                self.stats["vitality"] = self.get_max("vitality")

                self.instance.update_tier_info()

        def apply_trait_statsmod(self, trait, reverse=False):
            """Applies "stats_mod" field on characters.
            """
            for key in trait.mod_stats:
                if key not in ["disposition", "upkeep"]:
                    if not self.level%trait.mod_stats[key][1]:
                        self._mod_base_stat(key, trait.mod_stats[key][0]) if not reverse else self._mod_base_stat(key, -trait.mod_stats[key][0])

        def _mod_base_stat(self, key, value):
            # Modifies the first layer of stats (self.stats)
            if key in self.stats: # As different character types may come with different stats.
                value = self.settle_effects(key, value)

                val = self.stats[key] + value

                if key == 'health' and val <= 0:
                    if isinstance(self.instance, Player):
                        jump("game_over")
                    elif isinstance(self.instance, Char):
                        char = self.instance
                        kill_char(char)
                        return

                maxval = self.get_max(key)
                minval = self.min[key]

                if val >= maxval:
                    self.stats[key] = maxval
                    return
                elif val <= minval:
                    self.stats[key] = minval
                    return

                self.stats[key] = val

        def _mod_raw_skill(self, key, value, from__setattr__=True):
            """Modifies a skill.

            # DEVNOTE: THIS SHOULD NOT BE CALLED DIRECTLY! ASSUMES INPUT FROM PytCharacter.__setattr__
            # DEVNOTE: New arg attempts to correct that...

            Do we get the most needlessly complicated skills system award? :)
            Maybe we'll simplify this greatly in the future...
            """
            if key.islower():
                at = 0 # Action Skill...
            else:
                key = key.lower()
                at = 1 # Training (knowledge part) skill...

            current_full_value = self.get_skill(key)
            skill_max = SKILLS_MAX[key]
            if current_full_value >= skill_max: # Maxed out...
                return

            if from__setattr__:
                value -= self.skills[key][at]
            value *= max(0.5, min(self.skills_multipliers[key][at], 1.5))

            threshold = SKILLS_THRESHOLD[key]
            beyond_training = current_full_value - threshold

            if beyond_training > 0: # insufficient training... lessened increase beyond
                at_zero = skill_max - threshold
                value *= max(0.1, 1 - float(beyond_training)/at_zero)

            self.skills[key][at] += value

        def mod_full_skill(self, skill, value):
            """This spreads the skill bonus over both action and training.
            """
            self._mod_raw_skill(skill.lower(), value*(2/3.0), from__setattr__=False)
            self._mod_raw_skill(skill.capitalize(), value*(1/3.0), from__setattr__=False)

        def eval_inventory(self, inventory, weighted, target_stats, target_skills, exclude_on_skills, exclude_on_stats,
                           chance_func=None, min_value=-5, upto_skill_limit=False):
            """
            weigh items in inventory based on stats. weights per item will be added to weighted.

            inventory: the inventory to evaluate items from
            target_stats: a list of stats to consider for items
            target_skills: similarly, a list of skills
            exclude_on_stats: items will be excluded if stats in this list are negatively affected
            exclude_on_skills: similarly, a list of skills
            chance_func(): function that takes the item and returns a chance, between 0 and 100
            min_value: at what (negative) value the weight will become zero
            upto_skill_limit: whether or not to calculate bonus beyond training exactly
            """

            # call the functions for these only once
            stats = {'current_stat': {}, 'current_max': {}, 'skill': {}}
            for stat in target_stats:
                stats['current_stat'][stat] = self._get_stat(stat) # current stat value
                stats['current_max'][stat] = self.get_max(stat)   # current stat max

            for skill in self.skills:
                stats['skill'][skill] = self.get_skill(skill)

            # per item the nr of weighting criteria may vary. At the end all of them are averaged.
            # if an item has less than the most weights the remaining are imputed with 50 weights
            most_weights = {slot: 0 for slot in weighted}

            for item in inventory:

                if item.slot not in weighted:
                    continue

                # weights is a list of 0 to 100 values that will be averaged for the final weight, unless we break
                weights = chance_func(item) if chance_func else [item.eqchance]

                if weights is not None:
                    for stat, value in item.mod.iteritems():

                        if value < min_value and stat in exclude_on_stats:
                            break # break (in any case below) will cause 0 weights to be added for this item

                        if stat in stats['current_stat']:

                            # a new max may have to be considered
                            new_max = min(self.max[stat] + item.max[stat], self.lvl_max[stat]) if stat in item.max else stats['current_max'][stat]

                            if not new_max:
                                break

                            # what the new value would be:
                            new_stat = max(min(self.stats[stat] + self.imod[stat] + value, new_max), self.min[stat])

                            # add the fraction  increace / decrease
                            weights.append(50 + 100*(new_stat - stats['current_stat'][stat])/new_max)
                    else:
                        for stat, value in item.max.iteritems():

                            if not stat in exclude_on_stats:
                                continue

                            if stat in stats['current_max']:

                                new_max = min(self.max[stat] + value, self.lvl_max[stat])

                                new_stat = self.stats[stat] + self.imod[stat] + (item.mod[stat] if stat in item.mod else 0)

                                # if the stat does change, give weight for this
                                stat_change = new_stat - stats['current_stat'][stat]
                                if stat_change:
                                    if stat_change < min_value:
                                        break
                                    weights.append(50 + 100*stat_change/stats['current_max'][stat])
                                else:
                                    stat_remaining = new_max - stats['current_stat'][stat]
                                    # if training doesn't shift max, at least give a weight up to 1 for the increased max.
                                    # if max decreases, give a penalty, more severe if there is little stat remaining.
                                    weights.append(max(50 + value / max(stat_remaining + value, 1), 0))
                        else:
                            for skill, effect in item.mod_skills.iteritems():

                                if all(i <= 0 for i in effect) and skill in exclude_on_skills:
                                    break

                                if skill in target_skills:

                                    skill_remaining = SKILLS_MAX[skill] - stats['skill'][skill]
                                    if skill_remaining > 0:
                                        # calculate skill with mods applied, as in apply_item_effects() and get_skill()

                                        mod_action = self.skills[skill][0] + effect[3]
                                        mod_training = self.skills[skill][1] + effect[4]
                                        mod_skill_multiplier = self.skills_multipliers[skill][2] + effect[2]

                                        if upto_skill_limit: # more precise calculation of skill limits
                                            training_range = mod_training * 3
                                            beyond_training = mod_action - training_range

                                            if beyond_training >= 0:
                                                mod_training += training_range - mod_action + beyond_training/3.0

                                        mod_training += mod_action
                                        new_skill = mod_training*max(min(mod_skill_multiplier, 1.5), 0.5)
                                        if new_skill < min_value:
                                            break

                                        saturated_skill = max(stats['skill'][skill] + 100, new_skill)

                                        weights.append(50 + 100*(new_skill - stats['skill'][skill]) / saturated_skill)
                            else:
                                l = len(weights)

                                if l > most_weights[item.slot]:
                                    most_weights[item.slot] = l

                                weighted[item.slot].append([weights, item])
            return most_weights


    class Pronouns(_object):
        # Just to keep huge character class cleaner (smaller)
        # We can move this back before releasing...
        @property
        def mc_ref(self):
            if self._mc_ref is None:
                if self.status == "slave":
                    return "Master"
                else:
                    return hero.name
            else:
                return self._mc_ref

        @property
        def p(self):
            # Subject pronoun (he/she/it): (prolly most used so we don't call it 'sp'):
            if self.gender == "female":
                return "she"
            elif self.gender == "male":
                return "he"
            else:
                return "it"

        @property
        def pC(self):
            # Subject pronoun (he/she/it) capitalized:
            return self.p.capitalize()

        @property
        def op(self):
            # Object pronoun (him, her, it):
            if self.gender == "female":
                return "her"
            elif self.gender == "male":
                return "him"
            else:
                return "it"

        @property
        def opC(self):
            # Object pronoun (him, her, it) capitalized:
            return self.op.capitalize()

        @property
        def pp(self):
            # Possessive pronoun (his, hers, its):
            # This may 'gramatically' incorrect, cause things (it) cannot possess/own anything but knowing PyTFall :D
            if self.gender == "female":
                return "hers"
            elif self.gender == "male":
                return "his"
            else:
                return "its"

        @property
        def ppC(self):
            # Possessive pronoun (his, hers, its) capitalized::
            return self.pp.capitalize()

        @property
        def hs(self):
            if self.gender == "female":
                return "sister"
            else:
                return "brother"

        @property
        def hss(self):
            if self.gender == "female":
                return "sis"
            else:
                return "bro"


    ###### Character Classes ######
    class PytCharacter(Flags, Tier, JobsLogger, Pronouns):
        STATS = set()
        SKILLS = set(["vaginal", "anal", "oral", "sex", "strip", "service",
                      "refinement", "group", "bdsm", "dancing",
                      "bartending", "cleaning", "waiting", "management",
                      "exploration", "teaching", "swimming", "fishing",
                      "security"])
        # Used to access true, final, adjusted skill values through direct access to class, like: char.swimmingskill
        FULLSKILLS = set(skill + "skill" for skill in SKILLS)
        GEN_OCCS = set(["SIW", "Warrior", "Server", "Specialist"])
        STATUS = set(["slave", "free"])

        MOOD_TAGS = set(["angry", "confident", "defiant", "ecstatic", "happy",
                         "indifferent", "provocative", "sad", "scared", "shy",
                         "tired", "uncertain"])
        UNIQUE_SAY_SCREEN_PORTRAIT_OVERLAYS = ["zoom_fast", "zoom_slow", "test_case"]
        """Base Character class for PyTFall.
        """
        def __init__(self, arena=False, inventory=False, effects=False, is_worker=True):
            super(PytCharacter, self).__init__()
            self.img = ""
            self.portrait = ""
            self.gold = 0
            self.name = ""
            self.fullname = ""
            self.nickname = ""
            self._mc_ref = None # This is how characters refer to MC (hero). May depend on case per case basis and is accessed through obj.mc_ref property.
            self.height = "average"
            self.full_race = ""
            self.gender = "female"
            self.origin = ""

            self.AP = 3
            self.baseAP = 3
            self.reservedAP = 0

            # Locations and actions, most are properties with setters and getters.
            self._location = None # Present Location.
            self._workplace = None  # Place of work.
            self._home = None # Living location.
            self._action = None

            # Traits:
            self.upkeep = 0 # Required for some traits...

            self.traits = Traits(self)
            self.resist = SmartTracker(self, be_skill=False)  # A set of any effects this character resists. Usually it's stuff like poison and other status effects.

            # Relationships:
            self.friends = set()
            self.lovers = set()

            # Preferences:
            self.likes = set() # These are simple sets containing objects and possibly strings of what this character likes or dislikes...
            self.dislikes = set() # ... more often than not, this is used to compliment same params based of traits. Also (for example) to set up client preferences.

            # Arena relared:
            if arena:
                self.fighting_days = list() # Days of fights taking place
                self.arena_willing = False # Indicates the desire to fight in the Arena
                self.arena_permit = False # Has a permit to fight in main events of the arena.
                self.arena_active = False # Indicates that girl fights at Arena at the time.
                self._arena_rep = 0 # Arena reputation
                self.arena_stats = dict()
                self.combat_stats = dict()

            # Items
            if inventory:
                self.inventory = Inventory(15)
                self.eqslots = {
                    'head': False,
                    'body': False,
                    'cape': False,
                    'feet': False,
                    'amulet': False,
                    'wrist': False,
                    'weapon': False,
                    'smallweapon': False,
                    'ring': False,
                    'ring1': False,
                    'ring2': False,
                    'misc': False,
                    'consumable': None,
                }
                self.consblock = dict()  # Dict (Counter) of blocked consumable items.
                self.constemp = dict()  # Dict of consumables with temp effects.
                self.miscitems = dict()  # Counter for misc items.
                self.miscblock = list()  # List of blocked misc items.
                self.eqsave = [self.eqslots.copy(), self.eqslots.copy(), self.eqslots.copy()] # saved equipment states
                # List to keep track of temporary effect
                # consumables that failed to activate on cmax **We are not using this or at least I can't find this in code!
                # self.maxouts = list()

            # For workers (like we may not want to run this for mobs :) )
            if is_worker:
                Tier.__init__(self)
                JobsLogger.__init__(self)

            # Stat support Dicts:
            stats = {
                'charisma': [5, 0, 50, 60],          # means [stat, min, max, lvl_max]
                'constitution': [5, 0, 50, 60],
                'joy': [50, 0, 100, 200],
                'character': [5, 0, 50, 60],
                'reputation': [0, 0, 100, 100],
                'health': [100, 0, 100, 200],
                'fame': [0, 0, 100, 100],
                'mood': [0, 0, 1000, 1000], # not used...
                'disposition': [0, -1000, 1000, 1000],
                'vitality': [100, 0, 100, 200],
                'intelligence': [5, 0, 50, 60],

                'luck': [0, -50, 50, 50],

                'attack': [5, 0, 50, 60],
                'magic': [5, 0, 50, 60],
                'defence': [5, 0, 50, 60],
                'agility': [5, 0, 50, 60],
                'mp': [30, 0, 30, 50]
            }
            self.stats = Stats(self, stats=stats)
            self.STATS = set(self.stats.stats.keys())

            if effects:
                # Effects assets:
                self.effects = {
                'Poisoned': {"active": False, "penalty": False, "duration": False, 'desc': "Poison decreases health every day. Make sure you cure it as fast as possible."},
                'Slow Learner': {'active': False, 'desc': "-10% experience"},
                'Fast Learner': {'active': False, 'desc': "+10% experience"},
                "Introvert": {'active': False, 'desc': "Harder to increase and decrease disposition."},
                "Extrovert": {'active': False, 'desc': "Easier to increase and decrease disposition."},
                "Insecure": {'active': False, 'desc': "Significant changes in disposition also affect joy."},
                "Sibling": {'active': False, 'desc': "If disposition is low enough, it gradually increases over time."},
                "Assertive": {'active': False, 'desc': "If character stat is low enough, it increases over time."},
                "Diffident": {'active': False, 'desc': "If character stat is high enough, it slowly decreases over time."},
                'Food Poisoning': {'active': False, 'activation_count': 0, "desc": "Intemperance in eating or low quality food often lead to problems."},
                'Down with Cold': {'active': False, "desc": "Causes weakness and aches, will be held in a week or two."},
                "Unstable": {"active": False, "desc": "From time to time mood chaotically changes."},
                "Optimist": {"active": False, "desc": "Joy increases over time, unless it's too low. Grants immunity to Elation."},
                "Pessimist": {"active": False, "desc": "Joy decreases over time, unless it's already low enough. Grants immunity to Depression."},
                "Composure": {"active": False, "desc": "Over time joy decreases if it's too high and increases if it's too low."},
                "Kleptomaniac": {"active": False, "desc": "With some luck, her gold increases every day."},
                "Drowsy": {"active": False, "desc": "Rest restores more vitality than usual."},
                "Loyal": {"active": False, "desc": "Harder to decrease disposition."},
                "Lactation": {"active": False, "desc": "Her breasts produce milk. If she's your slave or lover, you will get a free sample every day."},
                "Vigorous": {"active": False, "desc": "If vitality is too low, it slowly increases over time."},
                "Silly": {"active": False, "desc": "If intelligence is high enough, it rapidly decreases over time."},
                "Intelligent": {"active": False, "desc": "If she feels fine, her intelligence increases over time."},
                "Fast Metabolism": {"active": False, "desc": "Any food is more effective than usual."},
                "Drunk": {"active": False, 'activation_count': 0, "desc": "It might feel good right now, but tomorrow's hangover is fast approaching (-1AP for every next drink)."},
                "Depression": {"active": False, "desc": "She's in a very low mood right now (-1AP).", 'activation_count': 0},
                "Elation": {"active": False, "desc": "She's in a very high mood right now (+1AP).", 'activation_count': 0},
                "Drinker": {"active": False, "desc": "Neutralizes the AP penalty of Drunk effect. But hangover is still the same."},
                "Injured": {"active": False, "desc": "Some wounds cannot be healed easily. In such cases special medicines are needed."},
                "Exhausted": {"active": False, "desc": "Sometimes anyone needs a good long rest.", 'activation_count': 0},
                "Impressible": {"active": False, "desc": "Easier to decrease and increase joy."},
                "Calm": {"active": False, "desc": "Harder to decrease and increase joy."},
                "Regeneration": {"active": False, "desc": "Restores some health every day."},
                "MP Regeneration": {"active": False, "desc": "Restores some mp every day."},
                "Small Regeneration": {"active": False, "desc": "Restores 10 health every day for 20 days."},
                "Blood Connection": {"active": False, "desc": "Disposition increases and character decreases every day."},
                "Horny": {"active": False, "desc": "She's in the mood for sex."},
                "Chastity": {"active": False, "desc": "Special enchantment preserves her virginity intact."},
                "Revealing Clothes": {"active": False, "desc": "Her clothes show a lot of skin, attracting views."},
                "Fluffy Companion": {"active": False, "desc": "All girls love cute cats, what often helps to increase disposition."}
                }

            # BE Bridge assets: @Review: Note: Maybe move this to a separate class/dict?
            self.besprite = None # Used to keep track of sprite displayable in the BE.
            self.beinx = 0 # Passes index from logical execution to SFX setup.
            self.beteampos = None # This manages team position bound to target (left or right on the screen).
            self.row = 1 # row on the battlefield, used to calculate range of weapons.
            self.front_row = True # 1 for front row and 0 for back row.
            self.betag = None # Tag to keep track of the sprite.
            self.dpos = None # Default position based on row + team.
            self.sopos = () # Status underlay position, which should be fixed.
            self.cpos = None # Current position of a sprite.
            self.besk = None # BE Show **Kwargs!
            # self.besprite_size = None # Sprite size in pixels. THIS IS NOW A PROPERTY!
            self.allegiance = None # BE will default this to the team name.
            self.controller = "player"
            self.beeffects = []
            self.can_die = False
            self.dmg_font = "red"
            self.status_overlay = [] # This is something I wanted to test out, trying to add tiny status icons somehow.

            self.attack_skills = SmartTracker(self)  # Attack Skills
            self.magic_skills = SmartTracker(self)  # Magic Skills
            self.default_attack_skill = battle_skills["Fist Attack"] # This can be overwritten on character creation!

            # Game world status:
            self.alive = True
            self._available = True

            self.jobpoints = 0

            # Say style properties:
            self.say_style = {"color": ivory}

            # We add Neutral element here to all classes to be replaced later:
            self.apply_trait(traits["Neutral"])

            self.say = None # Speaker...

        def __getattr__(self, key):
            stats = self.__dict__.get("stats", {})
            if key in self.STATS:
                return stats._get_stat(key)
            elif key.lower() in self.SKILLS:
                return stats._raw_skill(key)
            elif key in self.FULLSKILLS:
                return self.stats.get_skill(key[:-5])
            raise AttributeError("%r object has no attribute %r" %
                                          (self.__class__, key))

        def __setattr__(self, key, value):
            if key in self.STATS:
                # Primary stat dict modifier...
                value = value - self.stats._get_stat(key)
                self.stats._mod_base_stat(key, int(round(value)))
            elif key.lower() in self.SKILLS:
                self.__dict__["stats"]._mod_raw_skill(key, value)
            else:
                super(PytCharacter, self).__setattr__(key, value)

        # Money:
        def take_money(self, amount, reason="Other"):
            if amount <= self.gold:
                self.gold -= amount
                return True
            else:
                return False

        def add_money(self, amount, reason="Other"):
            self.gold += amount

        # Game assist methods:
        def set_status(self, s):
            if s not in ["slave", "free"]:
                raise Exception("{} status is not valid for {} with an id: {}".format(s, self.__class__, self.id))
            self.status = s

        def update_sayer(self):
            self.say = Character(self.nickname, show_two_window=True, show_side_image=self.show("portrait", resize=(120, 120)), **self.say_style)

        # Properties:
        @property
        def is_available(self):
            # Is this enought or should there be separate tracker properties for gameworld and player actions? This will prolly do for now.
            if not self.alive:
                return False
            if self.action == "Exploring":
                return False
            return self._available

        @property
        def basetraits(self):
            return self.traits.basetraits

        @property
        def gen_occs(self):
            # returns a list of general occupation from Base Traits only.
            return self.traits.gen_occs

        @property
        def occupations(self):
            """
            Formerly "occupation", will return a set of jobs that a worker may be willing to do based of her basetraits.
            Not decided if this should be strings, Trait objects of a combination of both.
            """
            allowed = set()
            for t in self.traits:
                if t.basetrait:
                    allowed.add(t)
                    allowed = allowed.union(t.occupations)
            return allowed

        @property
        def action(self):
            return self._action
        @action.setter
        def action(self, value):
            self._action = value

        @property
        def arena_rep(self):
            return self._arena_rep
        @arena_rep.setter
        def arena_rep(self, value):
            if value <= -500:
                self._arena_rep = - 500
            else:
                self._arena_rep = value

        # Locations related ====================>
        @property
        def location(self):
            # Physical location at the moment, this is not used a lot right now.
            # if all([self._location == hero, isinstance(self, Char), self.status == "free"]):
                # return "Own Dwelling"
            # elif self._location == hero: # We set location to MC in most cases, this may be changed soon?
                # return "Streets"
            # else:
            return self._location # Otherwise we use the
        # Not sure we require a setter here now that I've added home and workplaces.
        @location.setter
        def location(self, value):
            # *Adding some location code that needs to be executed always:
            # if value == "slavemarket":
                # self.status = "slave"
                # self.home = "slavemarket"
            self._location = value

        @property
        def workplace(self):
            return self._workplace
        @workplace.setter
        def workplace(self, value):
            self._workplace = value

        @property
        def home(self):
            return self._home
        @home.setter
        def home(self, value):
            """Home setter needs to add/remove actors from their living place.

            Checking for vacancies should be handle at functions that are setting
            homes.
            """
            if isinstance(self._home, HabitableLocation):
                self._home.inhabitants.remove(self)
            if isinstance(value, HabitableLocation):
                value.inhabitants.add(self)
            self._home = value

        # Alternative Method for modding first layer of stats:
        def add_exp(self, value, adjust=True):
            # Adds experience, adjusts it by default...
            if adjust:
                value = adjust_exp(self, value)
            self.exp += value

        def mod_stat(self, stat, value):
            self.stats._mod_base_stat(stat, value)

        def mod_skill(self, skill, value):
            self.stats._mod_raw_skill(skill, value, from__setattr__=False)

        def get_max(self, stat):
            return self.stats.get_max(stat)

        def adjust_exp(self, exp):
            '''
            Temporary measure to handle experience...
            '''
            return adjust_exp(self, exp)

        def get_skill(self, skill):
            return self.stats.get_skill(skill)

        @property
        def elements(self):
            return _list(e for e in self.traits if e.elemental)

        @property
        def exp(self):
            return self.stats.exp
        @exp.setter
        def exp(self, value):
            self.stats._mod_exp(value)

        @property
        def level(self):
            return self.stats.level
        @property
        def goal(self):
            return self.stats.goal

        # -------------------------------------------------------------------------------->
        # Show to mimic girls method behavior:
        @property
        def besprite_size(self):
            return get_size(self.besprite)

        def get_sprite_size(self, tag="vnsprite"):
            # First, lets get correct sprites:
            if tag == "battle_sprite":
                if self.height == "average":
                    resize = (200, 180)
                elif self.height == "tall":
                    resize = (200, 200)
                elif self.height == "short":
                    resize = (200, 150)
                else:
                    devlog.warning("Unknown height setting for %s" % self.id)
                    resize = (200, 180)
            elif tag == "vnsprite":
                if self.height == "average":
                    resize = (1000, 520)
                elif self.height == "tall":
                    resize = (1000, 600)
                elif self.height == "short":
                    resize = (1000, 400)
                else:
                    devlog.warning("Unknown height setting for %s" % self.id)
                    resize = (1000, 500)
            else:
                raise Exception("get_sprite_size got unknown type for resizing!")
            return resize

        ### Displaying images
        @property
        def path_to_imgfolder(self):
            if isinstance(self, rChar):
                return rchars[self.id]["_path_to_imgfolder"]
            else:
                return self._path_to_imgfolder

        def _portrait(self, st, at):
            if self.flag("fixed_portrait"):
                return self.flag("fixed_portrait"), None
            else:
                return self.show("portrait", self.get_mood_tag(), type="first_default", add_mood=False, cache=True, resize=(120, 120)), None

        def override_portrait(self, *args, **kwargs):
            kwargs["resize"] = kwargs.get("resize", (120, 120))
            kwargs["cache"] = kwargs.get("cache", True)
            if self.has_image(*args, **kwargs): # if we have the needed portrait, we just show it
                self.set_flag("fixed_portrait", self.show(*args, **kwargs))
            elif "confident" in args: # if not...
                if self.has_image("portrait", "happy"): # then we replace some portraits with similar ones
                    self.set_flag("fixed_portrait", self.show("portrait", "happy", **kwargs))
                elif self.has_image("portrait", "indifferent"):
                    self.set_flag("fixed_portrait", self.show("portrait", "indifferent", **kwargs))
            elif "suggestive" in args:
                if self.has_image("portrait", "shy"):
                    self.set_flag("fixed_portrait", self.show("portrait", "shy", **kwargs))
                elif self.has_image("portrait", "happy"):
                    self.set_flag("fixed_portrait", self.show("portrait", "happy", **kwargs))
            elif "ecstatic" in args:
                if self.has_image("portrait", "happy"):
                    self.set_flag("fixed_portrait", self.show("portrait", "happy", **kwargs))
                elif self.set_flag("fixed_portrait", self.show("portrait", "shy")):
                    self.set_flag("fixed_portrait", self.show("portrait", "shy", **kwargs))
            elif "shy" in args:
                if self.has_image("portrait", "uncertain"):
                    self.set_flag("fixed_portrait", self.show("portrait", "uncertain", **kwargs))
            elif "uncertain" in args:
                if self.has_image("portrait", "shy"):
                    self.set_flag("fixed_portrait", self.show("portrait", "shy", **kwargs))
            else: # most portraits will be replaced by indifferent
                if self.has_image("portrait", "indifferent"):
                    self.set_flag("fixed_portrait", self.show("portrait", "indifferent", **kwargs))

        def show_portrait_overlay(self, s, mode="normal"):
            self.say_screen_portrait_overlay_mode = s

            if not s in self.UNIQUE_SAY_SCREEN_PORTRAIT_OVERLAYS:
                interactions_portraits_overlay.change(s, mode)

        def hide_portrait_overlay(self):
            interactions_portraits_overlay.change("default")
            self.say_screen_portrait_overlay_mode = None

        def restore_portrait(self):
            self.say_screen_portrait_overlay_mode = None
            self.del_flag("fixed_portrait")

        def get_mood_tag(self):
            """
            This should return a tag that describe characters mood.
            We do not have a proper mood flag system at the moment so this is currently determined by joy and
            should be improved in the future.
            """
            # tags = list()
            # if self.fatigue < 50:
                # return "tired"
            # if self.health < 15:
                # return "hurt"
            if self.joy > 75:
                return "happy"
            elif self.joy > 40:
                return "indifferent"
            else:
                return "sad"

        def select_image(self, *tags, **kwargs):
            '''Returns the path to an image with the supplied tags or "".
            '''
            tagset = set(tags)
            exclude = kwargs.get("exclude", None)

            # search for images
            imgset = tagdb.get_imgset_with_all_tags(tagset)
            if exclude:
                imgset = tagdb.remove_excluded_images(imgset, exclude)

            # randomly select an image
            if imgset:
                return random.sample(imgset, 1)[0]
            else:
                return ""

        def has_image(self, *tags, **kwargs):
            """
            Returns True if image is found.
            exclude k/w argument (to exclude undesired tags) is expected to be a list.
            """
            tags = list(tags)
            tags.append(self.id)
            exclude = kwargs.get("exclude", None)

            # search for images
            if exclude:
                imgset = tagdb.get_imgset_with_all_tags(tags)
                imgset = tagdb.remove_excluded_images(imgset, exclude)
            else:
                imgset = tagdb.get_imgset_with_all_tags(tags)

            return bool(imgset)

        def show(self, *tags, **kwargs):
            '''Returns an image with the supplied tags.

            Under normal type of images lookup (default):
            First tag is considered to be most important.
            If no image with all tags is found,
            game will look for a combination of first and any other tag from second to last.

            Valid keyword arguments:
                resize = (maxwidth, maxheight)
                    Both dimensions are required
                default = any object (recommended: a renpy image)
                    If default is set and no image with the supplied tags could
                    be found, the value of default is returned and a warning is
                    printed to "devlog.txt".
                cache = load image/tags to cache (can be used in screens language directly)
                type = type of image lookup order (normal by default)
                types:
                     - normal = normal search behavior, try all tags first, then first tag + one of each tags taken from the end of taglist
                     - any = will try to find an image with any of the tags chosen at random
                     - first_default = will use first tag as a default instead of a profile and only than switch to profile
                     - reduce = try all tags first, if that fails, pop the last tag and try without it. Repeat until no tags remain and fall back to profile or default.
                add_mood = Automatically adds proper mood tag. This will not work if a mood tag was specified on request OR this is set to False
            '''
            maxw, maxh = kwargs.get("resize", (None, None))
            cache = kwargs.get("cache", False)
            label_cache = kwargs.get("label_cache", False)
            exclude = kwargs.get("exclude", None)
            type = kwargs.get("type", "normal")
            default = kwargs.get("default", None)

            if "-" in tags[0]:
                _path = "/".join([self.path_to_imgfolder, tags[0]])
                if renpy.loadable(_path):
                    return ProportionalScale(_path, maxw, maxh)
                else:
                    return ProportionalScale("content/gfx/interface/images/no_image.png", maxw, maxh)

            add_mood = kwargs.get("add_mood", True) # Mood will never be checked in auto-mode when that is not sensible
            if set(tags).intersection(self.MOOD_TAGS):
                add_mood = False

            pure_tags = list(tags)
            tags = list(tags)
            if add_mood:
                mood_tag = self.get_mood_tag()
                tags.append(mood_tag)
            original_tags = tags[:]
            imgpath = ""

            if not any([maxw, maxh]):
                raise Exception("Width or Height were not provided to an Image when calling .show method!\n Character id: {}; Action: {}; Tags: {}; Last Label: {}.".format(self.id, str(self.action), ", ".join(tags), str(last_label)))

            if label_cache:
                for entry in self.img_cache:
                    if entry[0] == tags and entry[1] == last_label:
                        return ProportionalScale(entry[2], maxw, maxh)

            if cache:
                for entry in self.cache:
                    if entry[0] == tags:
                         return ProportionalScale(entry[1], maxw, maxh)

            # Select Image (set imgpath)
            if type in ["normal", "first_default", "reduce"]:
                if add_mood:
                    imgpath = self.select_image(self.id, *tags, exclude=exclude)
                if not imgpath:
                    imgpath = self.select_image(self.id, *pure_tags, exclude=exclude)

                if type in ["normal", "first_default"]:
                    if not imgpath and len(pure_tags) > 1:
                        tags = pure_tags[:]
                        main_tag = tags.pop(0)
                        while tags and not imgpath:
                            descriptor_tag = tags.pop()

                            # We will try mood tag on the last lookup as well, it can do no harm here:
                            if not imgpath and add_mood:
                                imgpath = self.select_image(main_tag, descriptor_tag, self.id, mood_tag, exclude=exclude)
                            if not imgpath:
                                imgpath = self.select_image(main_tag, descriptor_tag, self.id, exclude=exclude)
                        tags = original_tags[:]

                        if type == "first_default" and not imgpath: # In case we need to try first tag as default (instead of profile/default) and failed to find a path.
                            if add_mood:
                                imgpath = self.select_image(main_tag, self.id, mood_tag, exclude=exclude)
                            else:
                                imgpath = self.select_image(main_tag, self.id, exclude=exclude)

                elif type == "reduce":
                    if not imgpath:
                        tags = pure_tags[:]
                        while tags and not imgpath:
                            # if len(tags) == 1: # We will try mood tag on the last lookup as well, it can do no harm here: # Resulted in Exceptions bacause mood_tag is not set properly... removed for now.
                                # imgpath = self.select_image(self.id, tags[0], mood_tag, exclude=exclude)
                            if not imgpath:
                                imgpath = self.select_image(self.id, *tags, exclude=exclude)
                            tags.pop()

                        tags = original_tags[:]

            elif type == "any":
                tags = pure_tags[:]
                shuffle(tags)
                # Try with the mood first:
                if add_mood:
                    while tags and not imgpath:
                        tag = tags.pop()
                        imgpath = self.select_image(self.id, tag, mood_tag, exclude=exclude)
                    tags = original_tags[:]
                # Then try 'any' behavior without the mood:
                if not imgpath:
                    tags = pure_tags[:]
                    shuffle(tags)
                    while tags and not imgpath:
                        tag = tags.pop()
                        imgpath = self.select_image(self.id, tag, exclude=exclude)
                    tags = original_tags[:]

            if imgpath == "":
                msg = "could not find image with tags %s"
                if not default:
                    # New rule (Default Battle Sprites):
                    if "battle_sprite" in pure_tags:
                        force_battle_sprite = True
                    else:
                        if add_mood:
                            imgpath = self.select_image(self.id, 'profile', mood_tag)
                        if not imgpath:
                            imgpath = self.select_image(self.id, 'profile')
                else:
                    devlog.warning(str(msg % sorted(tags)))
                    return default

            # If we got here without being able to find an image ("profile" lookup failed is the only option):
            if "force_battle_sprite" in locals(): # New rule (Default Battle Sprites):
                imgpath = "content/gfx/images/" + "default_{}_battle_sprite.png".format(self.gender)
            elif not imgpath:
                devlog.warning(str("Total failure while looking for image with %s tags!!!" % tags))
                imgpath = "content/gfx/interface/images/no_image.png"
            else: # We have an image, time to convert it to full path.
                imgpath = "/".join([self.path_to_imgfolder, imgpath])

            if label_cache:
                self.img_cache.append([tags, last_label, imgpath])

            if cache:
                self.cache.append([tags, imgpath])

            return ProportionalScale(imgpath, maxw, maxh)

        def get_img_from_cache(self, label):
            """
            Returns imgpath!!! from cache based on the label provided.
            """
            for entry in self.img_cache:
                if entry[1] == label:
                    return entry[2]

            return ""

        def get_vnsprite(self, mood=("indifferent")):
            """
            Returns VN sprite based on characters height.
            Useful for random events that use NV sprites, heigth in unique events can be set manually.
            ***This is mirrored in galleries testmode, this method is not acutally used.
            """
            return self.show("vnsprite", resize=self.get_sprite_size())

        # AP + Training ------------------------------------------------------------->
        def restore_ap(self):
            self.AP = self.get_free_ap()

        def get_ap(self):
            ap = 0
            base = 35
            c = self.constitution
            while c >= base:
                c -= base
                ap += 1
                if base == 35:
                    base = 100
                else:
                    base = base * 2

            if str(self.home) == "Studio Apartment":
                ap += 1

            return self.baseAP + ap

        def get_free_ap(self):
            """
            For next day calculations only! This is not useful for the game events.
            """
            return self.get_ap() - self.reservedAP

        def take_ap(self, value):
            """
            Removes AP of the amount of value and returns True.
            Returns False if there is not enough Action points.
            This one is useful for game events.
            """
            if self.AP - value >= 0:
                self.AP -= value
                return True
            return False

        def auto_training(self, kind):
            """
            Training, right now by NPCs.
            *kind = is a string refering to the NPC
            """
            # Any training:
            self.exp += self.adjust_exp(randint(20, max(25, self.luck)))

            if kind == "train_with_witch":
                self.magic += randint(1, 3)
                self.intelligence += randint(1, 2)
                self.mp += randint(7, 15)

                if dice(50):
                    self.agility += 1

            if kind == "train_with_aine":
                self.charisma += randint(1, 3)
                self.vitality += randint(10, 20)
                if dice(max(10, self.luck)):
                    self.reputation += 1
                    self.fame += 1
                if dice(1 + self.luck*0.05):
                    self.luck += randint(1, 2)

            if kind == "train_with_xeona":
                self.attack += randint(1, 2)
                self.defence += randint(1, 2)
                if dice(50):
                    self.agility += 1
                self.health += randint(10, 20)
                if dice(25 + max(5, int(self.luck/3))):
                    self.constitution += randint(1, 2)

        def get_training_price(self):
            return 500 + 500 * (self.level/5)

        # Logging and updating daily stats change on next day:
        def log_stats(self):
            self.stats.log = copy.copy(self.stats.stats)
            self.stats.log["exp"] = self.exp
            self.stats.log["level"] = self.level

        # Items/Equipment related, Inventory is assumed!
        def eq_items(self):
            """Returns a list of all equiped items."""
            if hasattr(self, "eqslots"):
                return self.eqslots.values()
            else:
                return []

        def add_item(self, item, amount=1):
            self.inventory.append(item, amount=amount)

        def remove_item(self, item, amount=1):
            self.inventory.remove(item, amount=amount)

        def remove_all_items(self):
            for i in self.inventory:
                self.inventory.remove(i.id, amount=has_items(i.id, [self]))

        def auto_buy(self, item=None, amount=1, equip=False):

            # handle request to auto-buy a particular item!
            # including forbidden for slaves items - it might be useful
            if item:
                if isinstance(item, basestring):
                    item = store.items[item]

                if item in all_auto_buy_items:
                    amount = min(amount, int(self.gold / item.price))

                    if amount != 0:
                        self.take_money(item.price * amount, reason="Items")
                        self.inventory.append(item, amount)
                        if equip:
                            self.equip(item)

                        return [item.id] * amount

                return []

            # otherwise if it's just a request to buy an item randomly

            # make sure that she'll NEVER buy an items that is in badtraits
            skip = set()
            goodtraits = []
            for t in self.traits:
                if t in trait_selections["badtraits"]:
                    # why the #*!:-@ is extend() in place and union not??
                    skip = skip.union(trait_selections["badtraits"][t])
                if t in trait_selections["goodtraits"]:
                    goodtraits.extend(trait_selections["goodtraits"][t])

            returns = []
            # high chance to try to buy an item she really likes based on traits
            if goodtraits and dice(80):

                i = random.randint(1, len(goodtraits))
                while i > 0:
                    pick = goodtraits[i-1]

                    # filter out too expensive ones
                    if pick.price <= self.gold:

                        # weapons not accepted for status
                        if self.status != "slave" or not (pick.slot in ("weapon", "smallweapon") or pick.type in ("armor", "scroll")):

                            # make sure that girl will never buy more than 5 of any item!
                            count = self.inventory[pick] if self.eqslots[pick.slot] != pick else self.inventory[pick] + 1
                            if pick.slot == "ring":
                                if self.eqslots["ring1"] == pick: count += 1
                                if self.eqslots["ring2"] == pick: count += 1

                                count += self.eqslots.values().count(pick)

                            penalty = pick.badness + count * 20
                            # badtraits skipped here (late test because the search takes time)
                            if penalty < 100 and dice(100 - penalty) and not pick in skip and self.take_money(pick.price, "Items"):

                                self.inventory.append(pick)
                                returns.append(pick.id)

                                amount -= 1
                                if amount == 0:
                                    return returns
                                break
                        i -= 1 # enough money, but not a lucky pick, just try next
                    else:
                        # if the pick is more than she can afford, next pick will be half as pricy
                        i = i // 2 # ..break if this floors to 0

            skip = skip.union(goodtraits) # the goodtrait items are only available in the 1st selection round

            # define selections
            articles = []
            # if she has no body slot items, she will try to buy a dress
            if not self.eqslots["body"] or all(i.slot != "body" for i in self.inventory):
                articles.append("body")

            # 30% (of the remaining) chance for her to buy any good restore item.
            if dice(30):
                articles.append("restore")

            # then a high chance to buy a snack, I assume that all chars can eat and enjoy normal food even if it's actually useless for them in terms of anatomy, since it's true for sex
            if ("Always Hungry" in self.traits and dice(80)) or self.vitality > 100 and dice(200 - self.vitality):
                articles.append("food")

            if amount > 2: #food doesn't count, it's not a big meal

                # define weighted choice for remaining articles - based on status and class
                choices = [("rest", 100)]
                dress_weight = 100

                # for slaves exclude all weapons, spells and armor
                if self.status != "slave":
                    if "Warrior" in self.occupations:
                        choices.append(("warrior", 100))

                        # if we still didn't pick the items, if the character has Warrior occupation, she may ignore dresses
                        dress_weight = 60 if self.occupations.issuperset(("SIW", "Server", "Specialist")) else 25

                    if "Caster" in self.occupations and auto_buy_items["scroll"]: # FIXME: remove 2nd part when we have scrolls.
                        choices.append(("scroll", 25))

                choices.append(("dress", dress_weight))
                choice_sum = sum(w for c, w in choices)

                # add remaining choices, based on (normalized) weighted chances
                for r in random.sample(xrange(choice_sum), amount - 2):
                    for c, w in choices:
                        r -= w
                        if r <= 0:
                            articles.append(c)
                            break
            else:
                # oopsie, selected too many already, fixing that here
                articles = articles[:amount]

            for article in articles:
                wares = auto_buy_items[article]

                i = random.randint(1, len(wares))
                while i > 0:
                    price, pick = wares[i-1]
                    if price <= self.gold:

                        count = self.inventory[pick] if self.eqslots[pick.slot] != pick else self.inventory[pick] + 1
                        if pick.slot == "ring":
                            if self.eqslots["ring1"] == pick: count += 1
                            if self.eqslots["ring2"] == pick: count += 1

                        penalty = pick.badness + count * 20
                        if penalty < 100 and dice(100 - penalty) and not pick in skip and self.take_money(pick.price, "Items"):
                            self.inventory.append(pick)
                            returns.append(pick.id)
                            break
                        i -= 1
                    else:
                        i = i // 2

            return returns

        def keep_chance(self, item):
            """
            return a list of chances, up to 100 indicating how much the person wants to hold on to a particular
            item. Only includes personal preferences, use inv.eval_inventory() to determine stats/skills.
            """

            if not item.eqchance or not can_equip(item, self):
                return [-1000000]

            chance = []
            when_drunk = 30
            appetite = 50

            for trait in self.traits:

                if trait in trait_selections["badtraits"] and item in trait_selections["badtraits"][trait]:
                    return [-1000000]

                if trait in trait_selections["goodtraits"] and item in trait_selections["goodtraits"][trait]:
                    chance.append(100)

                if trait == "Kamidere": # Vanity: wants pricy uncommon items
                    chance.append((100 - item.chance + min(item.price/10, 100))/2)

                elif trait == "Tsundere": # stubborn: what s|he won't buy, s|he won't wear.
                    chance.append(100 - item.badness)

                elif trait == "Bokukko": # what the farmer don't know, s|he won't eat.
                    chance.append(item.chance)

                elif trait == "Heavy Drinker":
                    when_drunk = 45

                elif trait == "Always Hungry":
                    appetite += 20

                elif trait == "Slim":
                    appetite -= 10

            if item.type == "permanent": # only allowed if also in goodtraits. but then we already returned 100
                return [-1000000]

            if item.slot == "consumable":

                if item in self.consblock or item in self.constemp:
                    return [-10]

                if item.type == "alcohol":

                    if self.effects['Drunk']['activation_count'] >= when_drunk:
                        return [-1]

                    if self.effects['Depression']['active']:
                        chance.append(30 + when_drunk)

                elif item.type == "food":

                    food_poisoning = self.effects['Food Poisoning']['activation_count']

                    if not food_poisoning:
                        chance.append(appetite)

                    else:
                        if food_poisoning >= 6:
                            return [-1]

                        chance.append((6-food_poisoning) * 9)

            elif item.slot == "misc":
                # If the item self-destructs or will be blocked after one use,
                # it's now up to the caller to stop after the first item of this kind that is picked.

                # no blocked misc items:
                if item.id in self.miscblock:
                    return [-1000000]

            chance.append(item.eqchance)
            return chance

        def equip(self, item, remove=True): # Equips the item
            """
            Equips an item to a corresponding slot or consumes it.
            remove: Removes from the inventory (Should be False if item is equipped from directly from a foreign inventory)
            **Note that the remove is only applicable when dealing with consumables, game will not expect any other kind of an item.
            """
            if isinstance(item, list):
                for it in item:
                    self.equip(it, remove)
                return

            if item.slot not in self.eqslots:
                devlog.warning(str("Unknown Items slot: %s, %s" % (item.slot, self.__class__.__name__)))
                return

            # This is a temporary check, to make sure nothing goes wrong:
            # Code checks during the equip method should make sure that the unique items never make it this far:
            if item.unique and item.unique != self.id:
                raise Exception("""A character attempted to equip unique item that was not meant for him/her.
                                   This is a flaw in game design, please report to out development team!
                                   Character: %s/%s, Item:%s""" % self.id, self.__class__, item.id)

            if item.sex not in ["unisex", self.gender]:
                devlog.warning(str("False character sex value: %s, %s, %s" % (item.sex, item.id, self.__class__.__name__)))
                return

            if item.slot == 'consumable':
                if item in self.consblock:
                    return

                if item.cblock:
                    self.consblock[item] = item.cblock
                if item.ctemp:
                    self.constemp[item] = item.ctemp
                if remove: # Needs to be infront of effect application for jumping items.
                    self.inventory.remove(item)
                self.apply_item_effects(item)

            elif item.slot == 'misc':
                if item in self.miscblock:
                    return

                if self.eqslots['misc']: # Unequip if equipped.
                    temp = self.eqslots['misc']
                    self.inventory.append(temp)
                    del(self.miscitems[temp])
                self.eqslots['misc'] = item
                self.miscitems[item] = item.mtemp
                self.inventory.remove(item)

            elif item.slot == 'ring':
                if not self.eqslots['ring']:
                    self.eqslots['ring'] = item
                elif not self.eqslots['ring1']:
                    self.eqslots['ring1'] = item
                elif not self.eqslots['ring2']:
                    self.eqslots['ring2'] = item
                else:
                    self.apply_item_effects(self.eqslots['ring'], direction=False)
                    self.inventory.append(self.eqslots['ring'])
                    self.eqslots['ring'] = self.eqslots['ring1']
                    self.eqslots['ring1'] = self.eqslots['ring2']
                    self.eqslots['ring2'] = item
                self.apply_item_effects(item)
                self.inventory.remove(item)

            else:
                # Any other slot:
                if self.eqslots[item.slot]: # If there is any item equipped:
                    self.apply_item_effects(self.eqslots[item.slot], direction=False) # Remove equipped item effects
                    self.inventory.append(self.eqslots[item.slot]) # Add unequipped item back to inventory
                self.eqslots[item.slot] = item # Assign new item to the slot
                self.apply_item_effects(item) # Apply item effects
                self.inventory.remove(item) # Remove item from the inventory

        def unequip(self, item, slot=None):
            if item.slot == 'misc':
                self.eqslots['misc'] = None
                del(self.miscitems[item])
                self.inventory.append(item)

            elif item.slot == 'ring':
                if slot:
                    self.eqslots[slot] = None
                elif self.eqslots['ring'] == item:
                    self.eqslots['ring'] = None
                elif self.eqslots['ring1'] == item:
                    self.eqslots['ring1'] = None
                elif self.eqslots['ring2'] == item:
                    self.eqslots['ring2'] = None
                else:
                    raise Exception("Error while unequiping a ring! (Girl)")
                self.inventory.append(item)
                self.apply_item_effects(item, direction=False)

            else:
                # Other slots:
                self.inventory.append(item)
                self.apply_item_effects(item, direction=False)
                self.eqslots[item.slot] = None

        def equip_chance(self, item):
            """
            return a list of chances, between 0 and 100 if the person has a preference to equip this item.
            If None is returned the item should not be used. This only includes personal preferences,
            Other factors, like stat bonuses may also have to be taken into account.
            """

            # if return is 0 the item should be skipped

            if not item.eqchance or not can_equip(item, self):
                return None

            chance = []
            when_drunk = 30
            appetite = 50

            for trait in self.traits:

                if trait in trait_selections["badtraits"] and item in trait_selections["badtraits"][trait]:
                    return None

                if trait in trait_selections["goodtraits"] and item in trait_selections["goodtraits"][trait]:
                    chance.append(100)

                if trait == "Kamidere": # Vanity: wants pricy uncommon items
                    chance.append((100 - item.chance + min(item.price/10, 100))/2)

                elif trait == "Tsundere": # stubborn: what s|he won't buy, s|he won't wear.
                    chance.append(100 - item.badness)

                elif trait == "Bokukko": # what the farmer don't know, s|he won't eat.
                    chance.append(item.chance)

                elif trait == "Heavy Drinker":
                    when_drunk = 45

                elif trait == "Always Hungry":
                    appetite += 20

                elif trait == "Slim":
                    appetite -= 10

            if item.type == "permanent": # only allowed if also in goodtraits. but then we already returned 100
                return None

            if item.slot == "consumable":

                if item in self.consblock or item in self.constemp:
                    return None

                if item.type == "alcohol":

                    if self.effects['Drunk']['activation_count'] >= when_drunk:
                        return None

                    if self.effects['Depression']['active']:
                        chance.append(30 + when_drunk)

                elif item.type == "food":

                    food_poisoning = self.effects['Food Poisoning']['activation_count']

                    if not food_poisoning:
                        chance.append(appetite)

                    else:
                        if food_poisoning >= 6:
                            return None

                        chance.append((6-food_poisoning) * 9)

            elif item.slot == "misc":
                # If the item self-destructs or will be blocked after one use,
                # it's now up to the caller to stop after the first item of this kind that is picked.

                # no blocked misc items:
                if item in self.miscblock:
                    return None

            chance.append(item.eqchance)
            return chance

        def equip_for(self, purpose):
            """
            This method will auto-equip slot items on per purpose basis!
            """
            returns = list()
            if self.eqslots["weapon"]:
                self.unequip(self.eqslots["weapon"])

            slots = store.EQUIP_SLOTS

            if purpose == "Combat":
                returns.extend(self.auto_equip(['health', 'mp', 'attack', 'magic',
                                                'defence', 'agility', "luck"],
                                                slots=slots, real_weapons=True))
            elif purpose == "Battle Mage":
                returns.extend(self.auto_equip(['health', 'mp', 'attack', 'magic'],
                               exclude_on_stats=["agility", "luck", 'defence', 'intelligence'],
                               slots=slots, real_weapons=True))
            elif purpose == "Barbarian":
                returns.extend(self.auto_equip(['health', 'attack', 'constitution', 'agility'],
                               exclude_on_stats=["luck"], slots=slots, real_weapons=True))
            elif purpose == "Wizard":
                returns.extend(self.auto_equip(['mp', 'magic', "luck", 'intelligence'],
                               exclude_on_stats=["health", 'defence'],
                               slots=slots, real_weapons=True))
            elif purpose == "Striptease":
                returns.extend(self.auto_equip(["charisma"], ["strip"],
                               exclude_on_stats=["health", "vitality", "mp", "joy"],
                               slots=slots))
            elif purpose == "Sex":
                returns.extend(self.auto_equip(["charisma"], ["vaginal", "anal", "oral"],
                               exclude_on_stats=["health", "vitality", "mp"], slots=slots))
            elif purpose == "Service":
                returns.extend(self.auto_equip(["charisma"], ["service"],
                               exclude_on_stats=["health", "vitality", "mp", "joy"],
                               slots=slots))
            else:
                devlog.warning("Supplied unknown purpose: %s to equip_for method for: %s, (Class: %s)" % (purpose,
                                                            self.name, self.__class__.__name__))
            return returns

        def auto_equip(self, target_stats, target_skills=None, exclude_on_skills=None,
                       exclude_on_stats=None, slots=None,
                       inv=None, real_weapons=False):
            """
            targetstats: expects a list of stats to pick the item
            targetskills: expects a list of skills to pick the item
            exclude_on_stats: items will not be used if stats in this list are being
                diminished by use of the item *Decreased the chance of picking this item
            exclude_on_skills: items will not be used if stats in this list are being
                diminished by use of the item *Decreased the chance of picking this item
            ==>   do not put stats/skills both in target* and in exclude_on_* !
            *default: All Stats - targetstats
            slots: a list of slots, contains just consumables by default
            inv: nventory to draw from.
            real_weapons: Do we equip real weapon types (*Broom is now considered a weapon as well)
            """

            # Prepair data:
            if not slots:
                slots = ["consumable"]

            weighted = {}
            for k in slots:
                if self.eqslots[k]:
                    item = self.eqslots[k]
                    if not equipment_access(self, item=item, silent=True, allowed_to_equip=False):
                        continue
                    self.unequip(item)

                weighted[k] = []

            if not inv:
                inv = self.inventory
            if not target_skills:
                target_skills = set()

            exclude_on_stats = set(exclude_on_stats) if exclude_on_stats else set()
            exclude_on_skills = set(exclude_on_skills) if exclude_on_skills else set()

            # allow a little stat/skill penalty, just make sure the net weight is positive.
            min_value = -5
            upto_skill_limit = False

            # how much stats weigh vs skills. To compare weight will be normalised to their max values.
            # skills have a overly high max (5000), so the ratio is tipped towards stats.
            #stat_vs_skill = 0.5

            #if traits["Athletic"]:
            #    stat_vs_skill /= 2 # preference for skills over stats

            #if traits["Nerd"]:
            #    stat_vs_skill *= 2 # preference for stats over skills


            #selectivity = 1 if traits["Messy"] or traits["Clumsy"] else 1.5

            #if traits["Smart"] or traits["Psychic"]:
            #    selectivity *= 2

            #last = max(int(len(picks) / selectivity), 1)

            # traits that may influence the item selection process
            for t in self.traits:

                # bad eyesightedness may cause inclusion of items with more penalty
                if t == "Bad Eyesight":
                    min_value = -10

                # a clumsy person may also select items not in target skill
                elif t == "Clumsy":
                    target_skills = set(self.stats.skills.keys())

                # a stupid person may also select items not in target stat
                elif t == "Stupid":
                    target_stats = set(self.stats)

                elif t == "Smart":
                    upto_skill_limit = True

            exclude_on_stats = exclude_on_stats.union(target_stats)
            exclude_on_skills = exclude_on_skills.union(target_skills)

            most_weights = self.stats.eval_inventory(inv, weighted, target_stats, target_skills,
                                                     exclude_on_skills, exclude_on_stats,
                                                     chance_func=self.equip_chance, min_value=min_value,
                                                     upto_skill_limit=upto_skill_limit)

            returns = list() # We return this list with all items used during the method.
            for slot, picks in weighted.iteritems():

                if not picks:
                    continue

                # if we need only one pick, store max and item in selected, otherwise prefilter items
                selected = [0, None] if slot != "consumable" and slot != "ring" else []

                # create averages for items
                for r in picks:
                    # devlog.warn("[%s/%s]: %s" % (r[1].slot, r[1].id, str(r[0])))

                    som = sum(r[0])

                    # impute with weights of 50 for items that have less weights
                    som += 50 * (len(r[0]) - most_weights[slot])

                    r[0] = som/most_weights[slot]
                    if r[0] > 0:
                        if slot != "consumable" and slot != "ring":
                            if slot == "weapon" and not real_weapons and not r[1].type.lower().startswith("nw"):
                                continue

                            if r[0] > selected[0]:
                                selected = r # store weight and item for the highest weight
                        else:
                            selected.append(r)

                if slot != "consumable" and slot != "ring":

                    item = selected[1]

                    if item:
                        inv.remove(item)
                        self.equip(item, remove=False)
                        returns.append(item.id)
                    continue

                # multiple consumables/rings can be taken.
                # consumables not filtered will also be iterated over multiple times

                for weight, item in sorted(selected, key=lambda x: x[0], reverse=True):
                    while self.equip_chance(item) != None:
                        inv.remove(item)
                        self.equip(item, remove=False)
                        returns.append(item.id)

                        if not item.id in inv.items:
                            break

                        for stat in item.mod:
                            if not stat in target_stats:
                                continue

                            if item.slot == "ring" or self.stats._get_stat(stat) < self.get_max(stat)*0.40:
                                break # may select it a 2nd time

                            # If stat is above 40% of max, behave more selective, to prevent wasting items.

                            remains = self.get_max(stat) - self.stats._get_stat(stat)

                            # if effect is larger than remaining required and item is expensive, we don't select it.
                            if remains > 0 or (item.price <= 100 or remains > item.get_stat_eq_bonus(self.stats, stat)):
                                break
                        else:
                            # item gives no stat benefit anymore. Also apply it once for each skill benefit
                            for skill in item.mod_skills:
                                if skill in target_skills:
                                    inv.remove(item)
                                    self.equip(item, remove=False)
                                    returns.append(item.id)
                            break # outer for loop

                        if not item.id in inv.items:
                            break

                    if slot == "ring":
                        slot = "ring1"
                        continue
                    if slot == "ring1":
                        slot = "ring2"
                        continue
            return returns

        def load_equip(self, eqsave):
            # load equipment from save, if possible

            for slot, desired_item in eqsave.iteritems():

                currently_equipped = self.eqslots[slot]
                if currently_equipped == desired_item:
                    continue

                # rings can be on other fingers. swapping them is allowed in any case
                if slot == "ring":

                    # if the wanted ring is on the next finger, or the next finger requires current ring, swap
                    if self.eqslots["ring1"] == desired_item or eqsave["ring1"] == currently_equipped:
                        (self.eqslots["ring1"], self.eqslots[slot]) = (self.eqslots[slot], self.eqslots["ring1"])

                        currently_equipped = self.eqslots[slot]
                        if currently_equipped == desired_item:
                            continue

                if slot == "ring" or slot == "ring1":

                    if self.eqslots["ring2"] == desired_item or eqsave["ring2"] == currently_equipped:
                        (self.eqslots["ring2"], self.eqslots[slot]) = (self.eqslots[slot], self.eqslots["ring2"])

                        currently_equipped = self.eqslots[slot]
                        if currently_equipped == desired_item:
                            continue

                # if we have something equipped, see if we're allowed to unequip
                if currently_equipped and equipment_access(self, item=currently_equipped, silent=True, allowed_to_equip=False):
                    self.unequip(item=currently_equipped, slot=slot)

                if desired_item:
                    # if we want something else and have it in inventory..
                    if not self.inventory[desired_item]:
                        continue

                    # ..see if we're allowed to equip what we want
                    if equipment_access(self, item=desired_item, silent=True):
                        if can_equip(item=desired_item, character=self, silent=False):
                            self.equip(desired_item)

        # Applies Item Effects:
        def apply_item_effects(self, item, direction=True, misc_mode=False):
            """Deals with applying items effects on characters.

            directions:
            - True: Apply Effects
            - False: Remove Effects
            """
            # Attacks/Magic -------------------------------------------------->
            # Attack Skills:
            attack_skills = getattr(item, "attacks", [])
            for battle_skill in attack_skills:
                if battle_skill not in store.battle_skills:
                    msg = "Item: {} applied invalid {} battle skill to: {} ({})!".format(item.id, battle_skill, self.fullname, self.__class__)
                    devlog.warning(msg)
                    continue
                else:
                    battle_skill = store.battle_skills[battle_skill]
                func = self.attack_skills.append if direction else self.attack_skills.remove
                func(battle_skill, False)
            if attack_skills:
                # Settle the default attack skill:
                default = self.default_attack_skill
                if len(self.attack_skills) > 1 and default in self.attack_skills:
                    self.attack_skills.remove(default)
                elif not self.attack_skills:
                    self.attack_skills.append(default)

            # Combat Spells:
            for battle_skill in item.add_be_spells + item.remove_be_spells:
                if battle_skill not in store.battle_skills:
                    msg = "Item: {} applied invalid {} battle skill to: {} ({})!".format(item.id, battle_skill, self.fullname, self.__class__)
                    devlog.warning(msg)
                    continue
                else:
                    battle_skill = store.battle_skills[battle_skill]
                if battle_skill.name in item.add_be_spells:
                    func = self.magic_skills.append if direction else self.magic_skills.remove
                else:
                    func = self.magic_skills.remove if direction else self.magic_skills.append
                func(battle_skill, False)

            # Taking care of stats: -------------------------------------------------->
            # Max Stats:
            for stat, value in item.max.items():
                # Reverse the value if appropriate:
                original_value = value
                if not direction:
                    value = -value

                if "Left-Handed" in self.traits and item.slot == "smallweapon":
                    self.stats.max[stat] += value*2
                elif "Left-Handed" in self.traits and item.slot == "weapon":
                    self.stats.max[stat] += int(value*.5)
                elif "Knightly Stance" in self.traits and stat == "defence" and item.type == "armor":
                    self.stats.max[stat] += int(value*1.3)
                elif "Berserk" in self.traits and stat == "defence":
                    self.stats.max[stat] += int(value*.5)
                elif "Berserk" in self.traits and stat == "attack":
                    self.stats.max[stat] += int(value*2)
                elif "Hollow Bones" in self.traits and stat == "agility" and original_value < 0:
                    pass
                elif "Elven Ranger" in self.traits and stat == "defence" and original_value < 0 and item.type in ["bow", "crossbow", "throwing"]:
                    pass
                elif "Sword Master" in self.traits and item.type == "sword":
                    self.stats.max[stat] += int(value*1.3)
                elif "Shield Master" in self.traits and item.type == "shield":
                    self.stats.max[stat] += int(value*1.3)
                elif "Dagger Master" in self.traits and item.type == "dagger":
                    self.stats.max[stat] += int(value*1.3)
                elif "Bow Master" in self.traits and item.type == "bow":
                    self.stats.max[stat] += int(value*1.3)
                else:
                    self.stats.max[stat] += value

            # Min Stats:
            for stat, value in item.min.items():
                # Reverse the value if appropriate:
                original_value = value
                if not direction:
                    value = -value

                if "Left-Handed" in self.traits and item.slot == "smallweapon":
                    self.stats.min[stat] += value*2
                elif "Left-Handed" in self.traits and item.slot == "weapon":
                    self.stats.min[stat] += int(value*0.5)
                elif "Knightly Stance" in self.traits and stat == "defence":
                    self.stats.min[stat] += int(value*1.3)
                elif "Berserk" in self.traits and stat == "defence":
                    self.stats.min[stat] += int(value*.5)
                elif "Berserk" in self.traits and stat == "attack":
                    self.stats.min[stat] += int(value*2)
                elif "Hollow Bones" in self.traits and stat == "agility" and original_value < 0:
                    pass
                elif "Elven Ranger" in self.traits and stat == "defence" and original_value < 0 and item.type in ["bow", "crossbow", "throwing"]:
                    pass
                elif "Sword Master" in self.traits and item.type == "sword":
                    self.stats.min[stat] += int(value*1.3)
                elif "Dagger Master" in self.traits and item.type == "dagger":
                    self.stats.min[stat] += int(value*1.3)
                elif "Shield Master" in self.traits and item.type == "shield":
                    self.stats.min[stat] += int(value*1.3)
                elif "Bow Master" in self.traits and item.type == "bow":
                    self.stats.min[stat] += int(value*1.3)
                else:
                    self.stats.min[stat] += value

            # Items Stats:
            for stat, value in item.mod.items():
                # Reverse the value if appropriate:
                original_value = value
                if not direction:
                    value = -value

                # This health thing could be handled differently (note for the post-beta refactor)
                if stat == "health" and self.health + value <= 0:
                    self.health = 1 # prevents death by accident...
                    continue

                if original_value < 0:
                    condition = True
                elif item.statmax and getattr(self, stat) >= item.statmax:
                    condition = False
                else:
                    condition = True

                if condition:
                    if stat == "gold":
                        if misc_mode and self.status == "slave":
                            temp = hero
                        else:
                            temp = self
                        if value < 0:
                            temp.take_money(-value, reason="Upkeep")
                        else:
                            temp.add_money(value, reason="Items")
                    elif stat == "exp":
                        self.exp += value
                    elif stat in ['health', 'mp', 'vitality', 'joy'] or (item.slot in ['consumable', 'misc'] and not (item.slot == 'consumable' and item.ctemp)):
                        if direction:
                            if self.effects['Fast Metabolism']['active'] and item.type == "food":
                                self.mod_stat(stat, (2*value))
                            elif "Summer Eternality" in self.traits and stat == "health" and value > 0:
                                self.mod_stat(stat, (int(0.35*value)))
                            elif "Winter Eternality" in self.traits and stat == "mp" and value > 0:
                                self.mod_stat(stat, (int(0.35*value)))
                            elif "Effective Metabolism" in self.traits and stat == "vitality" and value > 0:
                                if item.type == "food":
                                    self.mod_stat(stat, (int(2*value)))
                                else:
                                    self.mod_stat(stat, (int(1.5*value)))
                            elif "Magical Kin" in self.traits and stat == "mp" and value > 0:
                                if item.type == "alcohol":
                                    self.mod_stat(stat, (int(2*value)))
                                else:
                                    self.mod_stat(stat, (int(1.5*value)))
                            else:
                                self.mod_stat(stat, value)
                        else:
                            self.mod_stat(stat, value)
                    else:
                        if "Left-Handed" in self.traits and item.slot == "smallweapon":
                            self.stats.imod[stat] += value*2
                        elif "Left-Handed" in self.traits and item.slot == "weapon":
                            self.stats.imod[stat] += int(value*0.5)
                        elif "Knightly Stance" in self.traits and stat == "defence":
                            self.stats.imod[stat] += int(value*1.3)
                        elif "Berserk" in self.traits and stat == "defence":
                            self.stats.imod[stat] += int(value*0.5)
                        elif "Berserk" in self.traits and stat == "attack":
                            self.stats.imod[stat] += int(value*2)
                        elif "Hollow Bones" in self.traits and stat == "agility" and original_value < 0:
                            pass
                        elif "Elven Ranger" in self.traits and stat == "defence" and original_value < 0 and item.type in ["bow", "crossbow", "throwing"]:
                            pass
                        elif "Sword Master" in self.traits and item.type == "sword":
                            self.stats.imod[stat] += int(value*1.3)
                        elif "Dagger Master" in self.traits and item.type == "dagger":
                            self.stats.imod[stat] += int(value*1.3)
                        elif "Shield Master" in self.traits and item.type == "shield":
                            self.stats.imod[stat] += int(value*1.3)
                        elif "Bow Master" in self.traits and item.type == "bow":
                            self.stats.imod[stat] += int(value*1.3)
                        else:
                            try:
                                self.stats.imod[stat] += value
                            except:
                                raise Exception(item.id, stat)

            # Special modifiers based off traits:
            temp = ["smallweapon", "weapon", "body", "cape", "feet", "wrist", "head"]
            if "Royal Assassin" in self.traits and item.slot in temp:
                value = int(item.price*.01) if direction else -int(item.price*.01)
                self.stats.max["attack"] += value
                self.mod_stat("attack", value)
            elif "Armor Expert" in self.traits and item.slot in temp:
                value = int(item.price*.01) if direction else -int(item.price*.01)
                self.stats.max["defence"] += value
                self.mod_stat("defence", value)
            elif "Arcane Archer" in self.traits and item.type in ["bow", "crossbow", "throwing"]:
                max_val = int(item.max["attack"]*.5) if direction else -int(item.max["attack"]*.5)
                imod_val = int(item.mod["attack"]*.5) if direction else -int(item.mod["attack"]*.5)
                self.stats.max["magic"] += max_val
                self.stats.imod["magic"] += imod_val
            if direction and "Recharging" in self.traits and item.slot == 'consumable' \
                and not item.ctemp and not("mp" in item.mod):
                self.mod_stat("mp", 10)

            # Skills:
            for skill, data in item.mod_skills.items():
                if not self.stats.is_skill(skill):
                    msg = "'%s' item tried to apply unknown skill: %s!"
                    devlog.warning(str(msg % (item.id, skill)))
                    continue

                if not direction:
                    data = [-i for i in data]

                if not item.skillmax or (self.get_skill(skill) < item.skillmax): # Multi messes this up a bit.
                    s = self.stats.skills[skill] # skillz
                    sm = self.stats.skills_multipliers[skill] # skillz muplties
                    sm[0] += data[0]
                    sm[1] += data[1]
                    sm[2] += data[2]
                    s[0] += data[3]
                    s[1] += data[4]

            # Traits:
            for trait in item.removetraits + item.addtraits:
                if trait not in store.traits:
                    devlog.warning(str("Item: {} has tried to apply an invalid trait: {}!".format(item.id, trait)))

                if item.slot not in ['consumable', 'misc'] or (item.slot == 'consumable' and item.ctemp):
                    truetrait = False
                else:
                    truetrait = True

                if trait in item.addtraits:
                    func = self.apply_trait if direction else self.remove_trait
                else:
                    func = self.remove_trait if direction else self.apply_trait
                func(store.traits[trait], truetrait)

            # Effects:
            if hasattr(self, "effects"):
                if direction:
                    if item.slot == 'consumable' and item.type == 'food':
                        self.effects['Food Poisoning']['activation_count'] += 1
                        if self.effects['Food Poisoning']['activation_count'] >= 7 and not (self.effects['Food Poisoning']['active']):
                            self.enable_effect('Food Poisoning')

                    if item.slot == 'consumable' and item.type == 'alcohol':
                        self.effects['Drunk']['activation_count'] += item.mod["joy"]
                        if self.effects['Drunk']['activation_count'] >= 35 and not self.effects['Drunk']['active']:
                            self.enable_effect('Drunk')
                        elif self.effects['Drunk']['active'] and self.AP > 0 and not self.effects['Drinker']['active']:
                            self.AP -=1

                for effect in item.addeffects:
                    if direction and not self.effects[effect]['active']:
                        self.enable_effect(effect)
                    elif not direction and self.effects[effect]['active']:
                        self.disable_effect(effect)

                for effect in item.removeeffects:
                    if direction and self.effects[effect]['active']:
                        self.disable_effect(effect)

            # Jump away from equipment screen if appropriate:
            if getattr(store, "eqtarget", None) is self:
                if item.jump_to_label:
                    renpy.scene(layer="screens") # hides all screens
                    eqtarget.inventory.set_page_size(15)
                    hero.inventory.set_page_size(15)
                    jump(item.jump_to_label)

        def item_counter(self):
            # Timer to clear consumable blocks
            for item in self.consblock.keys():
                self.consblock[item] -= 1
                if self.consblock[item] <= 0:
                    del(self.consblock[item])

            # Timer to remove effects of a temp consumer items
            for item in self.constemp.keys():
                self.constemp[item] -= 1
                if self.constemp[item] <= 0:
                    self.apply_item_effects(item, direction=False)
                    del(self.constemp[item])

            # Counter to apply misc item effects and settle misc items conditions:
            for item in self.miscitems.keys():
                self.miscitems[item] -= 1
                if self.miscitems[item] <= 0:
                    # Figure out if we can pay the piper:
                    for stat, value in item.mod.items():
                        if value < 0:
                            if stat == "exp":
                                pass
                            elif stat == "gold":
                                if self.status == "slave":
                                    temp = hero
                                else:
                                    temp = self
                                if temp.gold + value < 0:
                                    break
                            else:
                                if getattr(self, stat) + value < self.stats.min[stat]:
                                    break
                    else:
                        self.apply_item_effects(item, misc_mode=True)

                        # For Misc item that self-destruct:
                        if item.mdestruct:
                            del(self.miscitems[item])
                            self.eqslots['misc'] = False
                            if not item.mreusable:
                                self.miscblock.append(item)
                            return

                        if not item.mreusable:
                            self.miscblock.append(item)
                            self.unequip(item)
                            return

                    self.miscitems[item] = item.mtemp

        # Trait methods *now for all characters:
        # Traits methods
        def apply_trait(self, trait, truetrait=True): # Applies trait effects
            self.traits.apply(trait, truetrait=truetrait)

        def remove_trait(self, trait, truetrait=True):  # Removes trait effects
            if self.effects['Chastity']['active'] and trait.id == "Virgin":
                pass
            else:
                self.traits.remove(trait, truetrait=truetrait)

        # Effects:
        ### Effects Methods
        def enable_effect(self, effect):
            if effect == "Poisoned" and "Artificial Body" not in self.traits:
                self.effects['Poisoned']['active'] = True
                self.effects['Poisoned']['duration'] = 0
                self.effects['Poisoned']['penalty'] = locked_random("randint", 5, 10)

            elif effect == "Unstable":
                self.effects['Unstable']['active'] = True
                self.effects['Unstable']['day_log'] = day
                self.effects['Unstable']['day_target'] = day + randint(2,4)
                self.effects['Unstable']['joy_mod'] = randint(20, 30)
                if dice(50):
                    self.effects['Unstable']['joy_mod'] = -self.effects['Unstable']['joy_mod']

            elif effect == "Optimist":
                self.effects['Optimist']['active'] = True

            elif effect == "Blood Connection":
                self.effects['Blood Connection']['active'] = True

            elif effect == "Horny":
                self.effects['Horny']['active'] = True

            elif effect == "Chastity":
                self.effects['Chastity']['active'] = True

            elif effect == "Revealing Clothes":
                self.effects['Revealing Clothes']['active'] = True

            elif effect == "Regeneration":
                self.effects['Regeneration']['active'] = True

            elif effect == "MP Regeneration":
                self.effects['MP Regeneration']['active'] = True

            elif effect == "Small Regeneration":
                self.effects['Small Regeneration']['active'] = True

            elif effect == "Fluffy Companion":
                self.effects['Fluffy Companion']['active'] = True

            elif effect == "Injured":
                self.effects['Injured']['active'] = True

            elif effect == "Exhausted":
                self.effects['Exhausted']['active'] = True

            elif effect == "Drinker":
                self.effects['Drinker']['active'] = True

            elif effect == "Silly":
                self.effects['Silly']['active'] = True

            elif effect == "Intelligent":
                self.effects['Intelligent']['active'] = True

            elif effect == "Depression":
                self.effects['Depression']['active'] = True

            elif effect == "Elation":
                self.effects['Elation']['active'] = True

            elif effect == "Pessimist":
                self.effects["Pessimist"]["active"] = True

            elif effect == "Vigorous":
                self.effects["Vigorous"]["active"] = True

            elif effect == "Composure":
                self.effects['Composure']['active'] = True

            elif effect == "Down with Cold":
                self.effects['Down with Cold']['active'] = True
                self.effects['Down with Cold']['count'] = day
                self.effects['Down with Cold']['duration'] = locked_random("randint", 6, 14)
                self.effects['Down with Cold']['health'] = randint(2, 5)
                self.effects['Down with Cold']['vitality'] = randint(5, 15)
                self.effects['Down with Cold']['joy'] = randint(2, 5)
                self.effects['Down with Cold']['healthy_again'] = day + self.effects['Down with Cold']['duration']

            elif effect == "Kleptomaniac":
                self.effects["Kleptomaniac"]['active'] = True

            elif effect == "Slow Learner":
                self.effects["Slow Learner"]['active'] = True

            elif effect == "Fast Learner":
                self.effects["Fast Learner"]['active'] = True

            elif effect == "Drowsy":
                self.effects["Drowsy"]['active'] = True

            elif effect == "Fast Metabolism":
                self.effects["Fast Metabolism"]["active"] = True

            elif effect == "Drunk":
                self.effects["Drunk"]["active"] = True

            elif effect == "Lactation":
                self.effects["Lactation"]['active'] = True

            elif effect == "Loyal":
                self.effects["Loyal"]['active'] = True

            elif effect == "Introvert":
                self.effects['Introvert']['active'] = True

            elif effect == "Impressible":
                self.effects['Impressible']['active'] = True

            elif effect == "Calm":
                self.effects['Calm']['active'] = True

            elif effect == "Insecure":
                self.effects['Insecure']['active'] = True

            elif effect == "Extrovert":
                self.effects['Extrovert']['active'] = True

            elif effect == "Sibling":
                self.effects['Sibling']['active'] = True

            elif effect == "Assertive":
                self.effects['Assertive']['active'] = True

            elif effect == "Diffident":
                self.effects['Diffident']['active'] = True

            elif effect == "Food Poisoning":
                self.effects['Food Poisoning']['active'] = True
                self.effects['Food Poisoning']['count'] = day
                self.effects['Food Poisoning']['health'] = randint(8, 12)
                self.effects['Food Poisoning']['vitality'] = randint(10, 25)
                self.effects['Food Poisoning']['joy'] = randint(8, 12)
                self.effects['Food Poisoning']['healthy_again'] = day + 2

        def disable_effect(self, effect):
            if effect == "Poisoned":
                for key in self.effects["Poisoned"]:
                    if key != "desc":
                        self.effects["Poisoned"][key] = False

            elif effect == "Unstable":
                for key in self.effects["Unstable"]:
                    if key != "desc":
                        self.effects["Unstable"][key] = False

            elif effect == "Optimist":
                self.effects['Optimist']['active'] = False

            elif effect == "Blood Connection":
                self.effects['Blood Connection']['active'] = False

            elif effect == "Horny":
                self.effects['Horny']['active'] = False

            elif effect == "Chastity":
                self.effects['Chastity']['active'] = False

            elif effect == "Revealing Clothes":
                self.effects['Revealing Clothes']['active'] = False

            elif effect == "Regeneration":
                self.effects['Regeneration']['active'] = False

            elif effect == "MP Regeneration":
                self.effects['MP Regeneration']['active'] = False

            elif effect == "Small Regeneration":
                self.effects['Small Regeneration']['active'] = False

            elif effect == "Fluffy Companion":
                self.effects['Fluffy Companion']['active'] = False

            elif effect == "Drinker":
                self.effects['Drinker']['active'] = False

            elif effect == "Injured":
                self.effects['Injured']['active'] = False

            elif effect == "Exhausted":
                for key in self.effects["Exhausted"]:
                    if key != "desc":
                        self.effects["Exhausted"][key] = False

            elif effect == "Silly":
                self.effects['Silly']['active'] = False

            elif effect == "Depression":
                for key in self.effects["Depression"]:
                    if key != "desc":
                        self.effects["Depression"][key] = False

            elif effect == "Elation":
                for key in self.effects["Elation"]:
                    if key != "desc":
                        self.effects["Elation"][key] = False

            elif effect == "Intelligent":
                self.effects['Intelligent']['active'] = False

            elif effect == "Vigorous":
                self.effects['Vigorous']['active'] = False

            elif effect == "Pessimist":
                self.effects["Pessimist"]["active"] = False

            elif effect == "Fast Metabolism":
                self.effects["Fast Metabolism"]["active"] = False

            elif effect == "Drunk":
                for key in self.effects["Drunk"]:
                    if key != "desc":
                        self.effects["Drunk"][key] = False

            elif effect == "Composure":
                self.effects['Composure']['active'] = False

            elif effect == "Down with Cold":
                for key in self.effects["Down with Cold"]:
                    if key != "desc":
                        self.effects["Down with Cold"][key] = False

            elif effect == "Kleptomaniac":
                self.effects["Kleptomaniac "]['active'] = False

            elif effect == "Slow Learner":
                self.effects["Slow Learner"]['active'] = False

            elif effect == "Fast Learner":
                self.effects["Fast Learner"]['active'] = False

            elif effect == "Introvert":
                self.effects['Introvert']['active'] = False

            elif effect == "Impressible":
                self.effects['Impressible']['active'] = False

            elif effect == "Calm":
                self.effects['Calm']['active'] = False

            elif effect == "Drowsy":
                self.effects['Drowsy']['active'] = False

            elif effect == "Lactation":
                self.effects['Lactation']['active'] = False

            elif effect == "Loyal":
                self.effects['Loyal']['active'] = False

            elif effect == "Extrovert":
                self.effects['Extrovert']['active'] = False

            elif effect == "Insecure":
                self.effects['Insecure']['active'] = False

            elif effect == "Sibling":
                self.effects['Sibling']['active'] = False

            elif effect == "Assertive":
                self.effects['Assertive']['active'] = False

            elif effect == "Diffident":
                self.effects['Diffident']['active'] = False

            elif effect == "Food Poisoning":
                for key in self.effects["Food Poisoning"]:
                    if key != "desc":
                        self.effects["Food Poisoning"][key] = False

        def apply_effects(self, effect):
            '''Called on next day, applies effects'''
            if effect == "Poisoned":
                self.effects['Poisoned']['duration'] += 1
                self.effects['Poisoned']['penalty'] += self.effects['Poisoned']['duration'] * 5
                if self.health > self.effects['Poisoned']['penalty']:
                    self.health -= self.effects['Poisoned']['penalty']
                else:
                    self.health = 1
                if self.effects['Poisoned']['duration'] > 10:
                    self.disable_effect('Poisoned')

            elif effect == "Unstable":
                unstable = self.effects['Unstable']
                unstable['day_log'] += 1
                if unstable['day_log'] == unstable['day_target']:
                    self.joy += unstable['joy_mod']
                    unstable['day_log'] = day
                    unstable['day_target'] = day + randint(2, 4)
                    unstable['joy_mod'] = randint(20, 30) if randrange(2) else -randint(20, 30)

            elif effect == "Optimist":
                if self.joy >= 30:
                    self.joy += 1

            elif effect == "Blood Connection":
                self.disposition += 1
                self.character -=1

            elif effect == "Regeneration":
                h = 0
                if "Summer Eternality" in self.traits:
                    h += int(self.get_max("health")*0.5)
                if h <= 0:
                    h = 1
                self.health += h

            elif effect == "MP Regeneration":
                h = 0
                if "Winter Eternality" in self.traits:
                    h += int(self.get_max("mp")*0.5)
                if h <= 0:
                    h = 1
                self.mp += h

            elif effect == "Small Regeneration":
                self.health += 10

            elif effect == "Depression":
                if self.joy >= 30:
                    self.disable_effect('Depression')
                else:
                    self.AP -= 1

            elif effect == "Elation":
                if self.joy < 95:
                    self.disable_effect('Elation')
                else:
                    self.AP += 1

            elif effect == "Pessimist":
                if self.joy > 80:
                    self.joy -= 2
                elif self.joy > 10:
                    self.joy -= 1

            elif effect == "Assertive":
                if self.character < self.get_max("character")*0.5:
                    self.character += 2

            elif effect == "Diffident":
                if self.character > self.get_max("character")*0.6:
                    self.character -= 1

            elif effect == "Composure":
                if self.joy < 50:
                    self.joy += 1
                elif self.joy > 70:
                    self.joy -= 1

            elif effect == "Vigorous":
                if self.vitality < self.get_max("vitality")*0.25:
                    self.vitality += randint(2, 3)
                elif self.vitality < self.get_max("vitality")*0.5:
                    self.vitality += randint(1, 2)

            elif effect == "Down with Cold":
                if self.effects['Down with Cold']['healthy_again'] <= self.effects['Down with Cold']['count']:
                    self.disable_effect('Down with Cold')
                    return
                if self.health > 50:
                    self.health -= self.effects['Down with Cold']['health']
                self.vitality -= self.effects['Down with Cold']['vitality']
                self.joy -= self.effects['Down with Cold']['joy']
                self.effects['Down with Cold']['count'] += 1
                if self.effects['Down with Cold']['healthy_again'] <= self.effects['Down with Cold']['count']:
                    self.disable_effect('Down with Cold')

            elif effect == "Kleptomaniac":
                if dice(self.luck+55):
                    self.add_money(randint(5, 25))

            elif effect == "Injured":
                if self.health > int(self.get_max("health")*0.2):
                    self.health = int(self.get_max("health")*0.2)
                if self.vitality > int(self.get_max("vitality")*0.5):
                    self.vitality = int(self.get_max("vitality")*0.5)
                self.AP -= 1
                self.joy -= 10

            elif effect == "Exhausted":
                self.vitality -= int(self.get_max("vitality")*0.2)

            elif effect == "Lactation": # TO DO: add milking activiies, to use this fetish more widely
                if self.health >= 30 and self.vitality >= 30:
                    if self.status == "slave" or check_lovers(self, hero):
                        if "Small Boobs" in self.traits:
                            hero.add_item("Bottle of Milk")
                        elif "Average Boobs" in self.traits:
                            hero.add_item("Bottle of Milk", randint(1, 2))
                        elif "Big Boobs" in self.traits:
                            hero.add_item("Bottle of Milk", randint(2, 3))
                        else:
                            hero.add_item("Bottle of Milk", randint(2, 5))
                    elif not(has_items("Bottle of Milk", [self])): # in order to not stack bottles of milk into free chars inventories they get only one, and only if they had 0
                        self.add_item("Bottle of Milk")

            elif effect == "Silly":
                if self.intelligence >= 200:
                    self.intelligence -= 20
                if self.intelligence >= 100:
                    self.intelligence -= 10
                elif self.intelligence >= 25:
                    self.intelligence -= 5
                else:
                    self.intelligence = 20

            elif effect == "Intelligent":
                if self.joy >= 75 and self.vitality >= self.get_max("vitality")*0.75 and self.health >= self.get_max("health")*0.75:
                    self.intelligence += 1

            elif effect == "Sibling":
                if self.disposition < 100:
                    self.disposition += 2
                elif self.disposition < 200:
                    self.disposition += 1


            elif effect == "Drunk":
                self.vitality -= self.effects['Drunk']['activation_count']
                if self.health > 50:
                    self.health -= 10
                self.joy -= 5
                self.mp -= 20
                self.disable_effect('Drunk')

            elif effect == "Food Poisoning":
                if self.effects['Food Poisoning']['healthy_again'] <= self.effects['Food Poisoning']['count']:
                    self.disable_effect('Food Poisoning')
                    return
                if self.health > 10:
                    self.health -= self.effects['Food Poisoning']['health']
                self.vitality -= self.effects['Food Poisoning']['vitality']
                self.joy -= self.effects['Food Poisoning']['joy']
                self.effects['Food Poisoning']['count'] += 1
                if self.effects['Food Poisoning']['healthy_again'] <= self.effects['Food Poisoning']['count']:
                    self.disable_effect('Food Poisoning')

        # Relationships:
        def is_friend(self, char):
            return char in self.friends

        def is_lover(self, char):
            return char in self.lovers

        # Post init and ND.
        def init(self):
            # Normalize character
            if not self.fullname:
                self.fullname = self.name
            if not self.nickname:
                self.nickname = self.name

            # add Character:
            if not self.say:
                self.update_sayer()

            if not self.origin:
                self.origin = choice(["Alkion", "PyTFall", "Crossgate"])

            # Stats log:
            self.log_stats()
            self.restore_ap()

        def next_day(self):
            self.jobpoints = 0

            # We assume this to be safe for any character...
            # Day counter flags:
            for flag in self.flags.keys():
                if flag.startswith("_day_countdown"):
                    self.down_counter(flag, value=1, min=0, delete=True)
                # Deleting _jobs flags once all jobs are complete.
                elif flag.startswith("_jobs"):
                    self.del_flag(flag)

            # Run the effects if they are available:
            if hasattr(self, "effects"):
                for key in self.effects:
                    if self.effects[key]['active']:
                        self.apply_effects(key)

            # Log stats to display changes on the next day (Only for chars to whom it's useful):
            if self in hero.chars:
                self.log_stats()

        def nd_auto_train(self, txt):
            if self.flag("train_with_witch"):
                if self.get_free_ap():
                    if hero.take_money(self.get_training_price(), "Training"):
                        self.auto_training("train_with_witch")
                        self.reservedAP += 1
                        txt.append("\nSuccessfully completed scheduled training with Abby the Witch!")
                    else:
                        txt.append("\nNot enough funds to train with Abby the Witch. Auto-Training will be disabled!")
                        self.del_flag("train_with_witch")
                        self.remove_trait(traits["Abby Training"])
                else:
                    s0 = "\nNot enough AP left in reserve to train with Abby the Witch."
                    s1 = "Auto-Training will not be disabled."
                    s2 = "{color=[red]}This character will start next day with 0 AP!){/color}"
                    txt.append(" ".join([s0, s1, s2]))

            if self.flag("train_with_aine"):
                if self.get_free_ap():
                    if hero.take_money(self.get_training_price(), "Training"):
                        self.auto_training("train_with_aine")
                        self.reservedAP += 1
                        txt.append("\nSuccessfully completed scheduled training with Aine!")
                    else:
                        txt.append("\nNot enought funds to train with Aine. Auto-Training will be disabled!")
                        self.del_flag("train_with_aine")
                        self.remove_trait(traits["Aine Training"])
                else:
                    s0 = "\nNot enough AP left in reserve to train with Aine."
                    s1 = "Auto-Training will not be disabled."
                    s2 = "{color=[red]}This character will start next day with 0 AP!){/color}"
                    txt.append(" ".join([s0, s1, s2]))

            if self.flag("train_with_xeona"):
                if self.get_free_ap():
                    if hero.take_money(self.get_training_price(), "Training"):
                        self.auto_training("train_with_xeona")
                        self.reservedAP += 1
                        txt.append("\nSuccessfully completed scheduled combat training with Xeona!")
                    else:
                        txt.append("\nNot enough funds to train with Xeona. Auto-Training will be disabled!")
                        self.remove_trait(traits["Xeona Training"])
                        self.del_flag("train_with_xeona")
                else:
                    s0 = "\nNot enough AP left in reserve to train with Xeona."
                    s1 = "Auto-Training will not be disabled."
                    s2 = "{color=[red]}This character will start next day with 0 AP!){/color}"
                    txt.append(" ".join([s0, s1, s2]))

        def nd_log_report(self, txt, img, flag_red, type='girlndreport'):
            # Change in stats during the day:
            charmod = dict()
            for stat, value in self.stats.log.items():
                if stat == "exp": charmod[stat] = self.exp - value
                elif stat == "level": charmod[stat] = self.level - value
                else: charmod[stat] = self.stats[stat] - value

            # Create the event:
            evt = NDEvent()
            evt.red_flag = flag_red
            evt.charmod = charmod
            evt.type = 'girlndreport'
            evt.char = self
            evt.img = img
            evt.txt = txt
            NextDayEvents.append(evt)


    class Mob(PytCharacter):
        """
        I will use ArenaFighter for this until there is a reason not to...
        """
        def __init__(self):
            super(Mob, self).__init__(arena=True)

            # Basic Images:
            self.portrait = ""
            self.battle_sprite = ""
            self.combat_img = ""

            self.controller = BE_AI(self)

        @property
        def besprite_size(self):
            webm_spites = mobs[self.id].get("be_webm_sprites", None)
            if webm_spites:
                return webm_spites["idle"][1]
            return get_size(self.besprite)

        def has_image(self, *tags):
            """
            Returns True if image is found.
            """
            return True

        def show(self, what, resize=(None, None), cache=True):
            if what in ["battle", "fighting"]:
                what = "combat"
            if what == "portrait":
                what = self.portrait
            elif what == "battle_sprite":
                # See if we can find idle animation for this...
                webm_spites = mobs[self.id].get("be_webm_sprites", None)
                if webm_spites:
                    return ImageReference(webm_spites["idle"][0])
                else:
                    what = self.battle_sprite
            elif what == "combat" and self.combat_img:
                what = self.combat_img
            else:
                what = self.battle_sprite

            if isinstance(what, ImageReference):
                return prop_resize(what, resize[0], resize[1])
            else:
                return ProportionalScale(what, resize[0], resize[1])

        def restore_ap(self):
            self.AP = self.baseAP + int(self.constitution / 20)

        def init(self):
            # Normalize character
            if not self.fullname:
                self.fullname = self.name
            if not self.nickname:
                self.nickname = self.name

            # If there are no basetraits, we add Warrior by default:
            if not self.traits.basetraits:
                self.traits.basetraits.add(traits["Warrior"])
                self.apply_trait(traits["Warrior"])

            self.arena_willing = True # Indicates the desire to fight in the Arena
            self.arena_permit = True # Has a permit to fight in main events of the arena.
            self.arena_active = True # Indicates that girl fights at Arena at the time.

            if not self.portrait:
                self.portrait = self.battle_sprite

            super(Mob, self).init()


    class Player(PytCharacter):
        def __init__(self):
            super(Player, self).__init__(arena=True, inventory=True, effects=True)

            self.img_db = None
            self.id = "mc" # Added for unique items methods.
            self.cache = list()
            self.gold = 20000
            self.name = 'Player'
            self.fullname = 'Player'
            self.nickname = 'Player'
            self._location = locations["Streets"]
            self.status = "free"
            self.gender = "male"

            # Player only...
            self.corpses = list() # Dead bodies go here until disposed off. Why the fuck here??? There gotta be a better place for dead chars than MC's class. We're not really using this atm anyway....

            self._buildings = list()
            self._chars = list()

            # TODO Doesn't look like this is in use anymore?
            self.guard_relay = {"bar_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                           "whore_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                           "club_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0}
                                           }

            for p in pytRelayProxyStore:
                p.reset(self)

            self.fin = Finances(self)

            # Team:
            self.team = Team(implicit=[self])
            self.team.name = "Player Team"

        # Fin Methods:
        def take_money(self, value, reason="Other"):
            return self.fin.take_money(value, reason)

        def add_money(self, value, reason="Other"):
            self.fin.add_money(value, reason)

        # Girls/Borthels/Buildings Ownership
        @property
        def buildings(self):
            """
            Returns a list of all buildings in heros ownership.
            """
            return self._buildings

        @property
        def dirty_buildings(self):
            """
            The buildings that can be cleaned.
            """
            return [building for building in self.buildings if isinstance(building, BuildingStats)]

        @property
        def famous_buildings(self):
            """
            The buildings that have reputation.
            """
            return [building for building in self.buildings if isinstance(building, FamousBuilding)]

        @property
        def upgradable_buildings(self):
            """
            The buildings that can be upgraded.
            """
            return [building for building in self.buildings if isinstance(building, UpgradableBuilding) or isinstance(building, UpgradableBuilding)]

        def add_building(self, building):
            if building not in self._buildings:
                self._buildings.append(building)

        def remove_building(self, building):
            if building in self._buildings:
                self._buildings.remove(building)
            else:
                raise Exception, "This building does not belong to the player!!!"

        @property
        def chars(self):
            """List of owned girls
            :returns: @todo
            """
            return self._chars

        def add_char(self, char):
            if char not in self._chars:
                self._chars.append(char)

        def remove_char(self, char):
            if char in self._chars:
                self._chars.remove(char)
            else:
                raise Exception, "This char (ID: %s) is not in service to the player!!!" % self.id

        # ----------------------------------------------------------------------------------
        # Show to mimic girls method behavior:
        # def has_image(self, *tags):
        #     """
        #     Returns True if image is found.
        #     """
        #     return True

        # def show(self, tag, resize=(None, None), cache=True):
        #     if tag == "battle":
        #         tag = "combat"
        #     if tag == "fighting":
        #         tag = "combat"
        #     if tag == "cportrait":
        #         tag = "cportrait"
        #     if tag == "sprofile":
        #         tag = "sprofile"
        #     if cache:
        #         for entry in self.cache:
        #             if entry[0] == tag:
        #                 return ProportionalScale(entry[1], resize[0], resize[1])
        #
        #     if tag in self.img_db:
        #         path = choice(self.img_db[tag])
        #     else:
        #         path = choice(self.img_db["battle_sprite"])
        #
        #     if cache:
        #         self.cache.append([tag, path])
        #
        #     img = ProportionalScale(path, resize[0], resize[1])
        #
        #     return img

        def nd_pay_taxes(self):
            txt = ""
            if calendar.weekday() == "Monday" and day != 1 and not config.developer:
                txt += "\nIt's time to pay taxes!\n"
                income = dict()
                businesses = [b for b in self.buildings if hasattr(b, "fin")]
                for b in businesses:
                    for _day in b.fin.game_fin_log:
                        if int(_day) > day - 7:
                            for key in b.fin.game_fin_log[_day][0]["private"]:
                                income[key] = income.get(key, 0) + b.fin.game_fin_log[_day][0]["private"][key]
                            for key in b.fin.game_fin_log[_day][0]["work"]:
                                income[key] = income.get(key, 0) + b.fin.game_fin_log[_day][0]["work"][key]

                income = sum(income.values())
                txt += "Over the past week your taxable income accounted for: {color=[gold]}%d Gold{/color}. " % income
                if self.fin.income_tax_debt:
                    txt += "You are indebted to the govenment: %d Gold." % self.fin.income_tax_debt
                txt += "\n"
                if income <= 5000:
                    txt += "You may concider yourself lucky as any sum below 5000 Gold is not taxable. Otherwise the government would have totally ripped you off :)"
                elif income <= 25000:
                    tax = int(round(income*0.1))
                    txt += "Your income tax for this week is %d. " % tax
                    if self.fin.income_tax_debt:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                        txt += "That makes it a total amount of: %d Gold. " % self.fin.income_tax_debt
                    else:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                    if self.take_money(self.fin.income_tax_debt, "Income Taxes"):
                        txt += "\nYou were able to pay that in full!\n"
                        self.fin.income_tax_debt = 0
                    else:
                        txt += "\nYou've did not have enough money... Be advised that if your debt to the government reaches 50000, they will start indiscriminately confiscate your property. (meaning that you will loose everything that you own at repo prices).\n"
                elif income <= 50000:
                    tax = int(round(income*0.2))
                    txt += "Your income tax for this week is %d. " % tax
                    if self.fin.income_tax_debt:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                        txt += "That makes it a total amount of: %d Gold. " % self.fin.income_tax_debt
                    else:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                    if self.take_money(self.fin.income_tax_debt, "Income Taxes"):
                        txt += "\nYou were able to pay that in full!\n"
                        self.fin.income_tax_debt = 0
                    else:
                        txt += "\nYou've did not have enough money... Be advised that if your debt to the government reaches 50000, they will start indiscriminately confiscate your property. (meaning that you will loose everything that you own at repo prices).\n"
                elif income <= 100000:
                    tax = int(round(income*0.3))
                    txt += "Your income tax for this week is %d. " % tax
                    if self.fin.income_tax_debt:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                        txt += "That makes it a total amount of: %d Gold. " % self.fin.income_tax_debt
                    else:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                    if self.take_money(self.fin.income_tax_debt, "Income Taxes"):
                        txt += "\nYou were able to pay that in full!\n"
                        self.fin.income_tax_debt = 0
                    else:
                        txt += "\nYou've did not have enough money... Be advised that if your debt to the government reaches 50000, they will start indiscriminately confiscate your property. (meaning that you will loose everything that you own at repo prices).\n"
                elif income <= 200000:
                    tax = int(round(income*0.4))
                    txt += "Your income tax for this week is %d. " % tax
                    if self.fin.income_tax_debt:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                        txt += "That makes it a total amount of: %d Gold. " % self.fin.income_tax_debt
                    else:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                    if self.take_money(self.fin.income_tax_debt, "Income Taxes"):
                        txt += "\nYou were able to pay that in full!\n"
                        self.fin.income_tax_debt = 0
                    else:
                        txt += "\nYou've did not have enough money... Be advised that if your debt to the government reaches 50000, they will start indiscriminately confiscate your property. (meaning that you will loose everything that you own at repo prices).\n"
                else:
                    tax = int(round(income*0.45))
                    txt += "Your income tax for this week is %d. " % tax
                    if self.fin.income_tax_debt:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                        txt += "That makes it a total amount of: %d Gold. " % self.fin.income_tax_debt
                    else:
                        self.fin.income_tax_debt = self.fin.income_tax_debt + tax
                    if self.take_money(self.fin.income_tax_debt, "Income Taxes"):
                        txt += "\nYou were able to pay that in full!\n"
                        self.fin.income_tax_debt = 0
                    else:
                        txt += "\nYou've did not have enough money... Be advised that if your debt to the government reaches 50000, they will start indiscriminately confiscate your property. (meaning that you will loose everything that you own at repo prices).\n"

                txt += choice(["\nWe're not done yet...\n", "\nProperty tax:\n", "\nProperty taxes next!\n"])
                b_tax = 0
                s_tax = 0
                for b in businesses:
                    b_tax += int(b.price*0.04)
                for char in self.chars:
                    if char.status == "slave":
                        s_tax += int(char.fin.get_price()*0.05)
                if b_tax:
                    txt += "Your property taxes for your real estate are: %d Gold. " % b_tax
                if s_tax:
                    txt += "For Slaves that you own, property tax is: %d Gold." % s_tax
                tax = b_tax + s_tax
                if tax:
                    txt += "\nThat makes it a total of {color=[gold]}%d Gold{/color}" % tax
                    if self.fin.property_tax_debt:
                        txt += " Don't worry, we didn't forget about your debt of %d Gold either. Yeap, there are just the two unevitable things in life: Death and Paying your tax on Monday!" % self.fin.property_tax_debt
                        self.fin.property_tax_debt += tax
                    else:
                        self.fin.property_tax_debt += tax
                    if self.take_money(self.fin.property_tax_debt, "Property Taxes"):
                        txt += "\nWell done, but your wallet feels a lot lighter now :)\n"
                        self.fin.property_tax_debt = 0
                    else:
                        txt += "\nYour payment failed...\n"
                else:
                    txt += "\nHowever, you do not own much...\n"

                total_debt = self.fin.income_tax_debt + self.fin.property_tax_debt
                if total_debt:
                    txt += "\n\nYour current total debt to the govenment is {color=[gold]}%d Gold{/color}!" % total_debt
                if total_debt > 50000:
                    txt += " {color=[red]}... And... your're pretty much screwed because it is above 50000!{/color} Your property will now be confiscated :("
                    all_properties = list()
                    for char in hero.chars:
                        if char.status == "slave":
                            all_properties.append(char)
                    for b in businesses:
                        all_properties.append(b)
                    shuffle(all_properties)
                    while total_debt and all_properties:
                        multiplier = choice([0.4, 0.5, 0.6])
                        confiscate = all_properties.pop()
                        # TODO taxes: This may need to be revised.
                        # Also as part of the above, account for businesses and upgrades.
                        if isinstance(confiscate, Building):
                            price = confiscate.price
                            if self.home == confiscate:
                                self.home = locations["Streets"]
                            if self.location == confiscate:
                                set_location(self, None)
                            self.remove_brothel(confiscate)
                            retire_chars_from_location(self.chars, confiscate)
                        elif isinstance(confiscate, Char):
                            price = confiscate.fin.get_price()
                            hero.remove_char(confiscate)
                            if confiscate in self.team:
                                self.team.remove(confiscate)
                            # locations:
                            confiscate.home = pytfall.sm
                            confiscate.workplace = None
                            confiscate.action = None
                            set_location(confiscate, char.home)

                        txt += choice(["\n%s has been confiscated for a price of %s of the original value. " % (confiscate.name, multiplier),
                                               "\nThose sobs took %s from you! " % confiscate.name,
                                               "\nYou've lost %s! If only you were better at managing your business... " % confiscate.name])
                        total_debt = total_debt - int(price*multiplier)
                        if total_debt > 0:
                            txt += "You are still required to pay %s Gold." % total_debt
                        else:
                            txt += "Your debt has been payed in full!"
                            if total_debt <= 0:
                                total_debt = -total_debt
                                txt += " You get a sum of %d Gold returned to you from the last repo!" % total_debt
                                hero.add_money(total_debt, reason="Other")
                                total_debt = 0
                        if not all_properties and total_debt:
                            txt += "\n You do not own anything that might be reposessed by the government..."
                            txt += " You've been declared bankrupt and your debt is now Null and Void!"
                        self.fin.income_tax_debt = 0
                        self.fin.property_tax_debt = 0
            return txt

        def next_day(self):
            # ND Logic....
            # Relay from GuardJob:

            img = 'profile'
            txt = []
            flag_red = False

            for event in self.guard_relay:
                for stat in self.guard_relay[event]["stats"]:
                    if stat == "exp":
                        self.exp += self.guard_relay[event]["stats"][stat]
                    elif stat in self.STATS:
                        self.mod_stat(stat, self.guard_relay[event]["stats"][stat])

            # -------------------->
            txt.append("Hero Report:\n\n")

            # Home location nd mods:
            loc = self.home
            try:
                mod = loc.daily_modifier
            except:
                raise Exception("Home location without daily_modifier field was set. ({})".format(loc))

            if mod > 0:
                txt.append("You've comfortably spent a night.")
            elif mod < 0:
                flag_red = True
                txt.append("{color=[red]}You should find some shelter for the night... it's not healthy to sleep outside.{/color}\n")

            for stat in ("health", "mp", "vitality"):
                mod_by_max(self, stat, mod)

            # Training with NPCs --------------------------------------->
            self.nd_auto_train(txt)

            # Finances related ---->
            self.fin.next_day()

            # Taxes:
            txt.append(self.nd_pay_taxes())

            # ------------
            self.nd_log_report(txt, img, flag_red, type='mcndreport')

            # -------------
            self.cache = list()
            self.item_counter()
            self.restore_ap()
            self.reservedAP = 0
            self.log_stats()

            self.guard_relay = {"bar_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                "whore_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                "club_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                }

            for p in pytRelayProxyStore:
                p.reset(self)

            self.arena_stats = dict()

            super(Player, self).next_day()


    class Char(PytCharacter):
        # wranks = {
                # 'r1': dict(id=1, name=('Rank 1: Kirimise', '(Almost beggar)'), price=0),
                # 'r2': dict(id=2, name=("Rank 2: Heya-Mochi", "(Low-class prostitute)"), price=1000, ref=45, exp=10000),
                # 'r3': dict(id=3, name=("Rank 3: Zashiki-Mochi", "(Middle-class Prostitute"), price=3000, ref=60, exp=25000),
                # 'r4': dict(id=4, name=("Rank 4: Tsuke-Mawashi", "(Courtesan)"), price=5000, ref=80, exp=50000),
                # 'r5': dict(id=5, name=("Rank 5: Chûsan", "(Famous)"), price=7500, ref=100, exp=100000),
                # 'r6': dict(id=6, name=("Rank 6: Yobidashi", "(High-Class Courtesan)"), price=10000, ref=120, exp=250000),
                # 'r7': dict(id=7, name=("Rank 7: Koshi", "(Nation famous)"), price=25000, ref=200, exp=400000),
                # 'r8': dict(id=8, name=("Rank 8: Tayu", "(Legendary)"), price=50000, ref=250, exp=800000)
            # }
        RANKS = {}
        def __init__(self):
            super(Char, self).__init__(arena=True, inventory=True, effects=True)
            # Game mechanics assets
            self.gender = 'female'
            self.race = ""
            self.desc = ""
            self.status = "slave"
            self._location = "slavemarket"

            self.rank = 1

            self.baseAP = 2

            # Can set character specific event for recapture
            self.runaway_look_event = "escaped_girl_recapture"

            self.nd_ap = 0 # next day action points
            self.gold = 0
            self.price = 500
            self.alive = True

            # Image related:
            self.cache = list()
            self.img_cache = list()
            self.picture_base = dict()

            self.nickname = ""
            self.fullname = ""

            # Relays for game mechanics
            # courseid = specific course id girl is currently taking -- DEPRECATED: Training now uses flags
            # wagemod = Percentage to change wage payout
            self.wagemod = 100

            # Guard job relay:
            self.guard_relay = {
                "bar_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                "whore_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                "club_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
            }

            # Set relays that use the RelayProxy:
            for p in pytRelayProxyStore:
                p.reset(self)

            # Unhappy/Depressed counters:
            self.days_unhappy = 0
            self.days_depressed = 0

            # Trait assets
            self.init_traits = list() # List of traits to be enabled on game startup (should be deleted in init method)

            # Autocontrol of girls action (during the next day mostly)
            # TODO lt: Enable/Fix (to work with new skills/traits) this!
            # TODO lt: (Move to a separate instance???)
            self.autocontrol = {
            "Rest": True,
            "Tips": False,
            "SlaveDriver": False,
            "Acts": {"normalsex": True, "anal": True, "blowjob": True, "lesbian": True},
            "S_Tasks": {"clean": True, "bar": True, "waitress": True},
            }

            # Auto-equip/buy:
            self.autobuy = False
            self.autoequip = False
            self.given_items = dict()

            # Actions:
            self.previousaction = ''

            self.txt = list()
            self.fin = Finances(self)

        def init(self):
            """Normalizes after __init__"""

            # Names:
            if not self.name:
                self.name = self.id
            if not self.fullname:
                self.fullname = self.name
            if not self.nickname:
                self.nickname = self.name

            # Base Class | Status normalization:
            if not self.traits.basetraits:
                pattern = create_traits_base(self.GEN_OCCS)
                for i in pattern:
                    self.traits.basetraits.add(i)
                    self.apply_trait(i)

            if self.status not in self.STATUS:
                if "Warrior" in self.occupations:
                    self.status = "free"
                else:
                    self.status = random.sample(self.STATUS, 1).pop()

            # Locations + Home + Status:
            # SM string --> object
            if self.location == "slavemarket":
                set_location(self, pytfall.sm)
            if self.location == "city":
                set_location(self, store.locations["City"])

            # Make sure all slaves that were not supplied custom locations string, find themselves in the SM
            if self.status == "slave" and (str(self.location) == "City" or not self.location):
                set_location(self, pytfall.sm)

            # if character.location == existing location, then she only can be found in this location
            if self.status == "free" and self.location == pytfall.sm:
                set_location(self, store.locations["City"])

            # Home settings:
            if self.location == pytfall.sm:
                self.home = pytfall.sm
            if self.status == "free":
                if not self.home:
                    self.home = locations["City Apartments"]

            # Wagemod:
            if self.status == 'slave':
                self.wagemod = 0
            else:
                self.wagemod = 100

            # Battle and Magic skills:
            if not self.attack_skills:
                self.attack_skills.append(self.default_attack_skill)

            # FOUR BASE TRAITS THAT EVERY GIRL SHOULD HAVE AT LEAST ONE OF:
            if not list(t for t in self.traits if t.personality):
                self.apply_trait(traits["Deredere"])
            if not list(t for t in self.traits if t.race):
                self.apply_trait(traits["Unknown"])
            if not list(t for t in self.traits if t.breasts):
                self.apply_trait(traits["Average Boobs"])
            if not list(t for t in self.traits if t.body):
                self.apply_trait(traits["Slim"])

            # Dark's Full Race Flag:
            if not self.full_race:
                self.full_race = str(self.race)

            # Second round of stats normalization:
            for stat in ["health", "joy", "mp", "vitality"]:
                setattr(self, stat, self.get_max(stat))

            # Arena:
            if "Warrior" in self.occupations and self not in hero.chars and self.arena_willing is not False:
                self.arena_willing = True

            # Settle auto-equip + auto-buy:
            if self.status != "slave":
                self.autobuy = True
                self.autoequip = True
            else:
                self.autoequip = True
            self.set_flag("day_since_shopping", 1)

            # add Character:
            self.update_sayer()

            self.say_screen_portrait = DynamicDisplayable(self._portrait)
            self.say_screen_portrait_overlay_mode = None

            super(Char, self).init()

        def update_sayer(self):
            self.say = Character(self.nickname, show_two_window=True, show_side_image=self, **self.say_style)

        def get_availible_pics(self):
            """
            Determines (per category) what pictures are availible for the fixed events (like during the jobs).
            This is ran once during the game startup, should also run in the after_load label...
            Meant to decrease the amount of checks during the Next Day jobs. Should be activated in post Alpha code review.
            PS: It's better to simply add tags to a set instead of booleans as dict values.
            """
            # Lets start with the normal sex category:
            if self.has_image("sex"):
                self.picture_base["sex"] = dict(sex=True)
            else: self.picture_base["sex"] = dict(sex=False) # This is not really required as this should be  taken care of by the show method, maybe for the fututre.

            # Lets check for the more specific tags:
            if self.build_image_base["sex"]["sex"]:
                if self.has_image("sex", "doggy"):
                    self.picture_base["sex"]["doggy"] = True
                else:
                    self.picture_base["sex"]["doggy"] = False
                if self.has_image("sex", "missionary"):
                    self.picture_base["sex"]["missionary"] = True
                else:
                    self.picture_base["sex"]["missionary"] = False

        ### Girls fin methods
        def take_money(self, value, reason="Other"):
            return self.fin.take_money(value, reason)

        def add_money(self, value, reason="Other"):
            self.fin.add_money(value, reason)

        # Logic assists:
        def allowed_to_view_personal_finances(self):
            if self.status == "slave":
                return True
            elif self.disposition > 900:
                return True
            return False

        ### Next Day Methods
        def restore(self):
            # Called whenever character needs to have on of the main stats restored.
            l = list()
            if self.autoequip:
                if self.health < self.get_max("health")*0.3:
                    l.extend(self.auto_equip(["health"]))
                if self.vitality < self.get_max("vitality")*0.2:
                    l.extend(self.auto_equip(["vitality"]))
                if self.mp < self.get_max("mp")*0.1:
                    l.extend(self.auto_equip(["mp"]))
                if self.joy < self.get_max("joy")*0.4:
                    l.extend(self.auto_equip(["joy"]))
            if l:
                self.txt.append("She used: %s %s during the day!" % (", ".join(l), plural("item", len(l))))
            return l

        def check_resting(self):
            # Auto-Rest should return a well rested girl back to work (or send them auto-resting!):
            txt = []
            if not isinstance(self.action, Rest):
                # This will set this char to AutoRest using normal checks!
                can_do_work(self, check_ap=False, log=txt)
            else: # Char is resting already, we can check if is no longer required.
                self.action.after_rest(self, txt)
            return "".join(txt)

        def next_day(self):
            # Local vars
            img = 'profile'
            txt = []
            flag_red = False
            flag_green = False

            # If escaped:
            if self in pytfall.ra:
                self.health -= randint(3, 5)
                txt.append("\n{color=[red]}This girl has escaped! Assign guards to search for her or do so yourself.{/color}\n\n")
                flag_red = True
            else:
                # Front text (Days employed)
                days = set_font_color(self.fullname, "green")
                if not self.flag("daysemployed"):
                    txt.append("{} has started working for you today! ".format(days))
                else:
                    txt.append("{} has been working for you for {} {}. ".format(days,
                                                                            self.flag("daysemployed"),
                                                                            plural("day", self.flag("daysemployed"))))
                self.up_counter("daysemployed")

                # Home location nd mods:
                loc = self.home
                mod = loc.daily_modifier

                # TODO se/Char.nd(): This can't be right? This is prolly set to the exploration log object.
                if self.action == "Exploring":
                    txt.append("\n{color=[green]}She is currently on the exploration run!{/color}\n")
                else:
                    if mod > 0:
                        txt.append("She has comfortably spent a night.")
                    elif mod < 0:
                        flag_red = True
                        txt.append("{color=[red]}You should find some shelter for your worker... it's not healthy to sleep outside.{/color}\n")

                    for stat in ("health", "mp", "vitality"):
                        mod_by_max(self, stat, mod)

                # Finances:
                # Upkeep:
                if in_training_location(self):
                    txt.append("Upkeep is included in price of the class your girl's taking. \n")
                elif self.action == "Exploring":
                    pass
                else:
                    # The whole upkeep thing feels weird, penalties to slaves are severe...
                    amount = self.fin.get_upkeep()

                    if amount < 0:
                        txt.append("She actually managed to save you some money ({color=[gold]}%d Gold{/color}) instead of requiring upkeep! Very convenient! \n" % (-amount))
                        hero.add_money(-amount, reason="Workers Upkeep")
                    elif hero.take_money(amount, reason="Workers Upkeep"):
                        self.fin.log_logical_expense(amount, "Upkeep")
                        if hasattr(self.workplace, "fin"):
                            self.location.fin.log_logical_expense(amount, "Workers Upkeep")
                        txt.append("You paid {color=[gold]}%d Gold{/color} for her upkeep. \n" % amount)
                    else:
                        if self.status != "slave":
                            self.joy -= randint(3, 5)
                            self.disposition -= randint(5, 10)
                            txt.append("\nYou failed to pay her upkeep, she's a bit cross with your because of that... \n")
                        else:
                            self.joy -= 20
                            self.disposition -= randint(25, 50)
                            self.health -= 10
                            self.vitality -= 25
                            txt.append("\nYou've failed to provide even the most basic needs for your slave. This will end badly... \n")

                # This whole routine is basically fucked and done twice or more. Gotta do a whole check of all related parts tomorrow.
                # Settle wages:
                img = self.fin.settle_wage(txt, img)

                tips = self.flag("_jobs_tips")
                if tips:
                    temp = choice(["Total tips earned: %d Gold. " % tips,
                                   "%s got %d Gold in tips. " % (self.nickname, tips)])
                    txt.append(temp)

                    if self.autocontrol["Tips"]:
                        temp = choice(["As per agreement, your girl gets to keep all her tips! This is a very good motivator. ",
                                       "She's happy to keep it. "])
                        txt.append(temp)

                        self.add_money(tips, reason="Tips")
                        self.fin.log_logical_expense(tips, "Tips")
                        if isinstance(self.workplace, Building):
                            self.workplace.fin.log_logical_expense(tips, "Tips")

                        self.disposition += (1 + round_int(tips*.05))
                        self.joy += (1 + round_int(tips*.025))
                    else:
                        temp = choice(["You take all of her tips for yourself. ",
                                       "You keep all of it. "])
                        txt.append(temp)
                        hero.add_money(tips, reason="Worker Tips")

                # ----------------------------------------------------------------->
                # The bit from here on will be disabled during exploration and other multi-day activities:

                # Training with NPCs ---------------------------------------------->
                if not self.action == "Exploring":
                    self.nd_auto_train(txt)

                    # Shopping (For now will not cost AP):
                    self.nd_autoshop(txt)
                    # --------------------------------->>>

                    self.restore()
                    self.check_resting()

                    # Unhappiness and related:
                    img = self.nd_joy_disposition_checks(txt, img)

            # Effects:
            if self.effects['Poisoned']['active']:
                txt.append("\n{color=[red]}This girl is suffering from the effects of Poison!{/color}\n")
                flag_red = True
            if all([not self.autobuy, self.status != "slave", self.disposition < 950]):
                self.autobuy = True
                txt.append("She will go shopping whenever it may please here from now on!\n")
            if all([self.status != "slave", self.disposition < 850, not self.autoequip]):
                self.autoequip = True
                txt.append("She will be handling her own equipment from now on!\n")



            # Prolly a good idea to throw a red flag if she is not doing anything:
            # I've added another check to make sure this doesn't happen if
            # a girl is in FG as there is always something to do there:
            if not self.action:
                flag_red = True
                txt.append("\n\n  -{color=[red]}Please note that she is not really doing anything productive!-{/color}\n")

            txt.append("{color=[green]}\n\n%s{/color}" % "\n".join(self.txt))

            self.nd_log_report(txt, img, flag_red, type='girlndreport')

            # Finances related:
            self.fin.next_day()

            # Resets and Counters:
            self.restore_ap()
            self.reservedAP = 0
            self.item_counter()
            self.txt = list()
            self.img_cache = list()
            self.cache = list()
            self.set_flag("day_since_shopping", self.flag("day_since_shopping") + 1)

            self.effects['Food Poisoning']['activation_count'] = 0
            self.guard_relay = {
                                "bar_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                "whore_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                "club_event": {"count": 0, "helped": list(), "stats": dict(), "won": 0, "lost": 0},
                                }

            # Reset relays that use the RelayProxy.
            for p in pytRelayProxyStore:
                p.reset(self)

            # And Finally, we run the parent next_day() method that should hold things that are native to all of it's children!
            super(Char, self).next_day()
            # else:
            #     super(Char, self).next_day()

        def nd_autoshop(self, txt):
            if all([# self.action in [None, "AutoRest", "Rest"], # Feels off, they can go shopping after work.
                    self.autobuy, self.flag("day_since_shopping") > 5,
                    self.gold > 1000, self.status != "slave"]):

                self.set_flag("day_since_shopping", 1)
                temp = choice(["\n\n%s decided to go on a shopping tour :)\n" % self.nickname,
                               "\n\n%s went to town to relax, take her mind of things and maybe even do some shopping!\n" % self.nickname])
                txt.append(temp)

                result = self.auto_buy(amount=randint(3, 7))
                if result:
                    temp = choice(["{color=[green]}She bought {color=[blue]}%s %s{/color} for herself. This brightened her mood a bit!{/color}\n\n"%(", ".join(result), plural("item",len(result))),
                                   "{color=[green]}She got her hands on {color=[blue]}%s %s{/color}! She's definitely in better mood because of that!{/color}\n\n"%(", ".join(result),
                                                                                                                                                                   plural("item", len(result)))])
                    txt.append(temp)
                    flag_green = True
                    self.joy += 5 * len(result)
                else:
                    temp = choice(["But she ended up not doing much else than window-shopping...\n\n",
                                   "But she could not find what she was looking for...\n\n"])
                    txt.append(temp)

        def nd_joy_disposition_checks(self, txt, img):
            if self.joy <= 25:
                txt.append("\n\nThis girl is unhappy!")
                img = self.show("profile", "sad", resize=(500, 600))
                self.days_unhappy += 1
            else:
                if self.days_unhappy - 1 >= 0:
                    self.days_unhappy -= 1

            if self.days_unhappy > 7 and self.status != "slave":
                txt.append("{color=[red]}She has left your employment because you do not give a rats ass about how she feels!{/color}")
                flag_red = True
                hero.remove_char(self)
                char.home = locations["City Apartments"]
                char.workplace = None
                char.action = None
                set_location(char, locations["City"])
            elif self.disposition < -500:
                if self.status != "slave":
                    txt.append("{color=[red]}She has left your employment because she no longer trusts or respects you!{/color}")
                    flag_red = True
                    img = self.show("profile", "sad", resize=(500, 600))
                    hero.remove_char(self)
                    char.home = locations["City Apartments"]
                    char.workplace = None
                    char.action = None
                    set_location(char, locations["City"])
                elif self.days_unhappy > 7:
                    if dice(50):
                        txt.append("\n{color=[red]}Took her own life because she could no longer live as your slave!{/color}")
                        img = self.show("profile", "sad", resize=(500, 600))
                        flag_red = True
                        self.health = 0
                    else:
                        txt.append("\n{color=[red]}Tried to take her own life because she could no longer live as your slave!{/color}")
                        img = self.show("profile", "sad", resize=(500, 600))
                        flag_red = True
                        self.health = 1

            # This is temporary code, better and more reasonable system is needed,
            # especially if we want different characters to befriend each other.

            # until we'll have means to deal with chars
            # with very low disposition (aka slave training), negative disposition will slowly increase
            if self.disposition < -200:
                self.disposition += randint(2, 5)
            if self.disposition < -150 and hero in self.friends:
                txt.append("\n {} is no longer friends with you...".format(self.nickname))
                end_friends(self, hero)
            if self.disposition > 400 and not hero in self.friends:
                txt.append("\n {} became pretty close to you.".format(self.nickname))
                set_friends(self, hero)
            if self.disposition < 500 and hero in self.lovers:
                txt.append("\n {} and you are no longer lovers...".format(self.nickname))
                end_lovers(self, hero)

            return img


    class rChar(Char):
        '''Randomised girls (WM Style)
        Basically means that there can be a lot more than one of them in the game
        Different from clones we discussed with Dark, because clones should not be able to use magic
        But random girls should be as good as any of the unique girls in all aspects
        It will most likely not be possible to write unique scripts for random girlz
        '''
        def __init__(self):
            super(rChar, self).__init__()


    class Customer(PytCharacter):
        def __init__(self, gender="male", caste="Peasant"):
            super(Customer, self).__init__()

            self.gender = gender
            self.caste = caste
            self.rank = ilists.clientCastes.index(caste)
            self.regular = False # Regular clients do not get removed from building lists as those are updated.

            # Traits activation:
            if dice(2):
                self.apply_trait(traits['Aggressive'])

            # self.seenstrip = False  # Seen striptease at least once
            # self.stripsatisfaction = 0  # Range from 0 to 100, extra bonus of goes above

            # self.traitmatched = False  # Sets to true if checks on next day to avoid another loop during the job.
            # self.favtraits = set()
            # self.favgirls = set()
            # self.favacts = set()
            # Alex, we should come up with a good way to set portrait depending on caste
            self.portrait = "" # path to portrait
            self.questpic = "" # path to picture used in quests
            self.act = ""
            self.pronoun = ""

            # Should we use money? @ presently not...
            self.cash = 0 # carried cash
            self.cashtospend = 0 # cash the customer is willing to spend

            # class battle stats
            # self.attack = randint(5, 40)
            # self.magic = randint(5, 40)
            # self.defence = randint(5, 40)
            # self.mp = randint(5, 40)
            # self.agility = randint(5, 40)

            # if "Aggressive" in self.traits:
                # self.attack += randint(5,20)
                # self.defence += randint(5,20)
                # self.magic += randint(5,20)
                # self.agility += randint(5,20)
                # self.mp += randint(5,20)

            # determine act and pronoun
            if self.gender == 'male':
                self.act = choice(["sex", "anal", "blowjob"])
                self.pronoun = 'He'

            elif self.gender == 'female':
                # self.act = choice(pytWhoringActs.female.keys())
                self.act = "lesbian"
                self.pronoun = 'She'

            # @Review: Temporary disabled (until we are ready to do complex client modeling, all clients assumed to have infinite money)
            # if caste in ('Beggar'):
                # self.cash = randint(30, 50)
                # self.fame = randint(0, 10)

                # self.attack += randint(5, 10)
                # self.magic += randint(5, 10)
                # self.defence += randint(5, 10)
                # self.mp += randint(5, 10)
                # self.agility += randint(5, 10)
            # elif caste in ('Peasant', 'Nomad'):
                # self.cash = randint(50, 80)
                # self.fame = randint(10, 30)

                # self.attack += randint(5, 15)
                # self.magic += randint(5, 15)
                # self.defence += randint(5, 15)
                # self.mp += randint(5, 15)
                # self.agility += randint(5, 15)
            # elif caste in ('Merchant'):
                # self.cash = randint(80, 120)
                # self.fame = randint(25, 65)

                # self.attack += randint(10, 15)
                # self.magic += randint(10, 15)
                # self.defence += randint(10, 15)
                # self.mp += randint(10, 15)
                # self.agility += randint(10, 15)
            # elif caste in ('Wealthy Merchant', 'Clerk'):
                # self.cash = randint(120, 150)
                # self.fame = randint(65, 100)

                # self.attack += randint(10, 20)
                # self.magic += randint(10, 20)
                # self.defence += randint(10, 20)
                # self.mp += randint(10, 20)
                # self.agility += randint(10, 20)
            # elif caste in ('Noble'):
                # self.cash = randint(150, 200)
                # self.fame = randint(95, 150)

                # self.attack += randint(15, 30)
                # self.magic += randint(15, 30)
                # self.defence += randint(15, 30)
                # self.mp += randint(15, 30)
                # self.agility += randint(15, 30)
            # elif caste in ('Royal'):
                # self.cash = randint(200, 250)
                # self.fame = randint(120, 200)

                # self.attack += randint(25, 40)
                # self.magic += randint(25, 40)
                # self.defence += randint(25, 40)
                # self.mp += randint(25, 40)
                # self.agility += randint(25, 40)
            # else:
                # self.cash = 100
                # notify(u">>Warning<< Unknown caste: '%s'" % caste)
            # determine cash the customer is willing to spend
            # poor customers should be willing to spend all of it, or not go
            # into a brothel in the first place
            # self.cashtospend = min((self.cash/2 + 30), self.cash)

        # Want to see striptease method:
        def wts_strip(self, girl):
            # Just in the mood for striptease / Overlapping traits / Fame:
            if self.wtsstrip or self.favtraits.intersection(girl.traits) or girl.fame >= self.fame:
                # self.seenstrip = True
                return True
            else:
                return False


    class NPC(Char):
        """There is no point in this other than an ability to check for instances of NPCs
        """
        def __init__(self):
            super(NPC, self).__init__()
