from utils import (hex2int, int2bytes, Substitution, SPELL_TABLE,
                   SPELLBANS_TABLE, name_to_bytes, utilrandom as random)

spelldict = {}
spellnames = {}
f = open(SPELL_TABLE)
for line in f:
    line = line.strip()
    while '  ' in line:
        line = line.replace('  ', ' ')
    value, strength, name = tuple(line.split(','))
    spellnames[hex2int(value)] = name
f.close()

spellbans = {}
f = open(SPELLBANS_TABLE)
for line in f:
    line = line.strip()
    if line[0] == '#':
        continue
    spellid, modifier, name, ban = tuple(line.split(','))
    if ban == "ban":
        modifier = int(modifier) * -1
    spellbans[hex2int(spellid)] = int(modifier)
f.close()


class SpellBlock:
    def __init__(self, spellid, filename):
        self.spellid = spellid
        if self.spellid in spellbans and spellbans[self.spellid] < 0:
            self.valid = False
        else:
            self.valid = True
        self.name = spellnames[self.spellid]
        self.pointer = 0x46AC0 + (14 * spellid)
        f = open(filename, 'r+b')

        f.seek(self.pointer)
        targeting = ord(f.read(1))
        self.targeting = targeting
        self.target_random = targeting & 0x80
        self.target_enemy_default = targeting & 0x40
        self.target_group = targeting & 0x20
        self.target_auto = targeting & 0x10
        self.target_group_default = targeting & 0x08
        self.target_everyone = targeting & 0x04
        self.target_one_side_only = targeting & 0x02
        self.target_one = targeting & 0x01

        f.seek(self.pointer+1)
        self.elements = ord(f.read(1))
        self.elemental = self.elements > 0

        f.seek(self.pointer+2)
        effect1 = ord(f.read(1))
        self.physical = effect1 & 0x01
        self.miss_if_death_prot = effect1 & 0x02
        self.target_dead = effect1 & 0x04
        self.invert_undead = effect1 & 0x08
        self.randomize_target = effect1 & 0x10
        self.ignore_defense = effect1 & 0x20
        self.no_split_damage = effect1 & 0x40
        self.abort_on_allies = effect1 & 0x80

        f.seek(self.pointer+3)
        self.dmgtype = ord(f.read(1))
        self.outsidebattle = self.dmgtype & 0x01
        self.unreflectable = self.dmgtype & 0x02
        self.learnifcast = self.dmgtype & 0x04
        self.enablerunic = self.dmgtype & 0x08
        self.unknown = self.dmgtype & 0x10
        self.retargetdead = self.dmgtype & 0x20
        self.casterdies = self.dmgtype & 0x40
        self.concernsmp = self.dmgtype & 0x80

        f.seek(self.pointer+4)
        effect2 = ord(f.read(1))
        self.healing = effect2 & 0x01
        self.draining = effect2 & 0x02
        self.cure_status = effect2 & 0x04
        self.invert_status = effect2 & 0x08
        self.uses_stamina = effect2 & 0x10
        self.unblockable = effect2 & 0x20
        self.level_spell = effect2 & 0x40
        self.percentage = effect2 & 0x80

        f.seek(self.pointer+5)
        self.mp = ord(f.read(1))
        f.seek(self.pointer+6)
        self.power = ord(f.read(1))
        f.seek(self.pointer+7)
        self.accuracy = ord(f.read(1))
        f.seek(self.pointer+9)
        self.special = ord(f.read(1))
        f.seek(self.pointer+10)
        statuses = map(ord, f.read(4))
        self.death = statuses[0] & 0x80
        self.petrify = statuses[0] & 0x40
        self.condemned = statuses[1] & 0x1
        self.statuses = statuses
        self.has_status = sum([bin(b).count("1") for b in statuses])
        f.close()

    def __cmp__(self, other):
        if other is None:
            return 1
        return self.spellid - other.spellid

    def __hash__(self):
        return self.spellid

    @property
    def unrageable(self):
        return (self.is_blitz or self.is_swdtech or self.is_slots or
                not self.valid)

    @property
    def is_blitz(self):
        return self.spellid in xrange(0x5D, 0x65)

    @property
    def is_swdtech(self):
        return self.spellid in xrange(0x55, 0x5D)

    @property
    def is_esper(self):
        return self.spellid in xrange(0x36, 0x51)

    @property
    def is_slots(self):
        return self.spellid in xrange(0x7D, 0x83)

    def fix_reflect(self, filename):
        self.dmgtype |= 0x02
        f = open(filename, 'r+b')
        f.seek(self.pointer+3)
        f.write(chr(self.dmgtype))
        f.close()

    def rank(self):
        if self.power >= 1 and not self.percentage and not self.draining:
            power = self.power
            baseline = power
        else:
            power = None
            baseline = 20

        if self.accuracy:
            baseline = baseline * 0.9

        if self.target_enemy_default or \
                (self.target_everyone and not
                 self.target_one_side_only):
            if power:
                if self.ignore_defense:
                    baseline = baseline * 2
                if self.elemental:
                    baseline = baseline * 0.75
                if self.no_split_damage:
                    baseline = baseline * 1.5
                if self.invert_undead:
                    baseline = baseline * 0.75
                if self.uses_stamina:
                    baseline = baseline * 0.75

            if self.power and self.draining:
                baseline = baseline * 2

            if self.physical:
                baseline = baseline * 0.75
            if self.unblockable:
                baseline = baseline * 1.25
            if self.has_status:
                baseline = baseline * 1.25

            if self.miss_if_death_prot:
                if self.death:
                    baseline = baseline * 3.5
                elif self.petrify:
                    baseline = baseline * 3
                elif self.condemned:
                    baseline = baseline * 1
                elif self.percentage:
                    baseline = baseline * 1
                else:
                    baseline = baseline * 2
            elif self.petrify and not power:
                baseline = baseline * 3
            elif self.petrify:
                baseline = baseline * 1.5

        else:
            if self.death:
                baseline = baseline * 0.1

        if self.healing or not self.target_enemy_default:
            baseline = baseline * 0.5
        if self.level_spell:
            baseline = baseline * 0.25

        if self.spellid in spellbans:
            baseline += abs(spellbans[self.spellid])

        return int(baseline)


class CommandBlock:
    def __init__(self, pointer, start, end, menu, textptr, name, target):
        self.pointer = hex2int(pointer)
        self.start = hex2int(start)
        self.end = hex2int(end)
        self.menu = hex2int(menu)
        self.textptr = hex2int(textptr)
        self.name = name.lower()
        self.target = target.lower()
        self.id = None

    @property
    def size(self):
        return self.end - self.start

    def set_id(self, i):
        self.id = i
        self.proppointer = 0xFFE00 + (i*2)

    @property
    def usable_as_imp(self):
        return self.properties & 0x4

    @property
    def can_be_mimicked(self):
        return self.properties & 0x2

    @property
    def usable_by_gogo(self):
        return self.properties & 0x1

    def read_properties(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.proppointer)
        self.properties = ord(f.read(1))
        assert not self.properties & 0xF0
        self.targeting = ord(f.read(1))
        f.close()

    def write_properties(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.proppointer)
        f.write(chr(self.properties))
        f.write(chr(self.targeting))
        f.close()

    def setpointer(self, value, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        bytestring = "".join(map(chr, int2bytes(value, length=2)))
        f.write(bytestring)
        f.close()

    def unsetmenu(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.menu)
        bytestring = "".join(map(chr, [0x95, 0x77]))
        f.write(bytestring)
        f.close()

    def newname(self, text, filename):
        text = text.strip().replace(' ', '')
        text = text[:7]
        self.name = text
        text = name_to_bytes(text, 7)

        f = open(filename, 'r+b')
        f.seek(self.textptr)
        f.write("".join(map(chr, text)))
        f.close()

    def set_bit(self, pointer, filename, unset=False):
        bit = self.id % 8
        byte = 1 << bit
        offset = self.id / 8
        f = open(filename, 'r+b')
        f.seek(pointer + offset)
        old = ord(f.read(1))
        if unset:
            byte = old & (0xFF ^ byte)
        else:
            byte = old | byte
        f.seek(pointer + offset)
        f.write(chr(byte))

    def unset_retarget(self, filename):
        self.set_bit(0x24E46, filename, unset=True)

    def set_retarget(self, filename):
        self.set_bit(0x24E46, filename)

    def allow_while_confused(self, filename):
        self.set_bit(0x204D0, filename)

    def allow_while_berserk(self, filename):
        self.set_bit(0x204D4, filename)

    def disallow_while_berserk(self, filename):
        self.set_bit(0x204D4, filename, unset=True)


def get_ranked_spells(filename=None, magic_only=False):
    if spelldict:
        spells = sorted(spelldict.values(), key=lambda s: s.spellid)
    else:
        spells = [SpellBlock(i, filename) for i in xrange(0xFF)]
        for s in spells:
            spelldict[s.spellid] = s

    if magic_only:
        spells = [s for s in spells if s.spellid < 0x36]

    spells = sorted(spells, key=lambda i: i.rank())
    return spells


def get_spell(spellid):
    return spelldict[spellid]


class SpellSub(Substitution):
    def __init__(self, spellid):
        self.spellid = spellid
        self.bytestring = [0xA9, self.spellid, 0x85, 0xB6, 0xA9,
                           0x02, 0x85, 0xB5, 0x4C, 0x5F, 0x17]


def get_spellsets(spells=None):
    spellsets = {}
    spellset_bans = []
    spells = [s for s in spells if s.spellid not in spellset_bans]
    spellsets['Chaos'] = []
    spellsets['Magic'] = range(0, 0x36)
    spellsets['Black'] = range(0, 0x18)
    spellsets['White'] = range(0x2D, 0x36)
    spellsets['Gray'] = range(0x18, 0x2D)
    spellsets['Esper'] = range(0x36, 0x51)
    spellsets['Sword'] = range(0x55, 0x5D)
    spellsets['Blitz'] = range(0x5D, 0x65)
    spellsets['Geo'] = range(0x65, 0x75)
    spellsets['Beast'] = range(0x75, 0x7D)
    spellsets['Lore'] = range(0x8B, 0xA3)
    spellsets['Rare'] = range(0x7D, 0x83) + range(0xA3, 0xEE)
    elementals = [s for s in spells if bin(s.elements).count('1') == 1]
    spellsets['Fire'] = [s for s in elementals if s.elements & 1]
    spellsets['Ice'] = [s for s in elementals if s.elements & 2]
    spellsets['Bolt'] = [s for s in elementals if s.elements & 4]
    spellsets['Bio'] = [s for s in elementals if s.elements & 8]
    spellsets['Wind'] = [s for s in elementals if s.elements & 0x10]
    spellsets['Pearl'] = [s for s in elementals if s.elements & 0x20]
    spellsets['Earth'] = [s for s in elementals if s.elements & 0x40]
    spellsets['Water'] = [s for s in elementals if s.elements & 0x80]
    spellsets['Elem'] = [s for s in spells if s.elements and
                         s.spellid not in spellsets['Black']]
    spellsets['Nuke'] = [s for s in spells if s.power and not any(
        [s.elements, s.percentage, s.physical, s.healing])]
    spellsets['Heal'] = [s for s in spells if s.healing]
    spellsets['Phys'] = [s for s in spells if s.physical]
    spellsets['Curse'] = [s for s in spells if all(
        [s.target_enemy_default, not s.miss_if_death_prot, not s.power])]
    spellsets['Bless'] = [s for s in spells if not any(
        [s.target_enemy_default, s.power, s.spellid == 0xA4])]
    spellsets['Drain'] = [s for s in spells if s.draining]
    spellsets['Mana'] = [s for s in spells if s.concernsmp]
    spellsets['Death'] = ([s for s in spells if s.miss_if_death_prot and
                           not s.percentage and s.has_status]
                          + [get_spell(s) for s in [0x46, 0xC4, 0xE2, 0xE5]])
    spellsets['Heavy'] = [s for s in spells if s.miss_if_death_prot and
                          s.percentage]
    spellsets['All'] = [s for s in spells if s.target_everyone and
                        not s.target_one_side_only]
    spellsets['Party'] = [s for s in spells if s.target_group_default and
                          not s.target_enemy_default]
    spellsets['Tek'] = ([0x18, 0x6E, 0x70, 0x7D, 0x7E] + range(0x86, 0x8B) +
                        [0xA7, 0xB1] + range(0xB4, 0xBA) + [0x91, 0x9A] +
                        [0xBF, 0xCD, 0xD1, 0xD4, 0xD7, 0xDD, 0xE3])
    spellsets['Time'] = [0x10, 0x11, 0x12, 0x13, 0x19, 0x1B, 0x1F, 0x20, 0x22,
                         0x26, 0x27, 0x28, 0x2A, 0x2B, 0x34, 0x89, 0x9B, 0xA0,
                         0xC9, 0xDF]

    for key, value in spellsets.items():
        if not value:
            continue
        if type(value[0]) is int:
            spellsets[key] = [s for s in spells if s.spellid in value]
        spellsets[key] = sorted(set(spellsets[key]), key=lambda s: s.spellid)

    return spellsets


class RandomSpellSub(Substitution):
    @property
    def template(self):
        if self.wild:
            return self.get_wild()
        template = [0x20, 0x5A, 0x4B,        # get random number
                    0x29, None,              # AND the result
                    0xAA,                    # TAX
                    0xBF, None, None, None,  # load byte from $addr + X
                    0x85, 0xB6, 0xA9, 0x02, 0x85, 0xB5,
                    0x64, 0xB8, 0x64, 0xB9,  # clear targets
                    0x20, 0xC1, 0x19,  # JSR $19C1
                    0x20, 0x51, 0x29,  # JSR $2951
                    0x4C, 0x5F, 0x17,
                    ]
        return template

    def get_wild(self):
        template = [0x20, 0x5A, 0x4B,        # get random number
                    0x85, 0xB6, 0xA9, 0x02, 0x85, 0xB5,
                    0x64, 0xB8, 0x64, 0xB9,  # clear targets
                    0x20, 0xC1, 0x19,  # JSR $19C1
                    0x20, 0x51, 0x29,  # JSR $2951
                    0x4C, 0x5F, 0x17,
                    ]
        return template

    @property
    def size(self):
        if self.wild:
            return len(self.template)
        return len(self.template) + len(self.spells)

    def generate_bytestring(self):
        self.bytestring = list(self.template)
        if self.wild:
            return self.bytestring

        pointer = self.location + len(self.bytestring)
        self.bytestring[4] = len(self.spells) - 1
        assert self.bytestring[4] in [(2**i)-1 for i in range(1, 8)]
        a, b, c = pointer >> 16, (pointer >> 8) & 0xFF, pointer & 0xFF
        self.bytestring[7:10] = [c, b, a]
        if None in self.bytestring:
            raise Exception("Bad pointer calculation.")
        self.bytestring += sorted([s.spellid for s in self.spells])

    def write(self, filename):
        super(RandomSpellSub, self).write(filename)

    def set_spells(self, valid_spells, spellsets=None, spellclass=None):
        spellsets = spellsets or get_spellsets(spells=valid_spells)
        spellclass = spellclass or random.choice(spellsets.keys())
        self.name = spellclass
        if spellclass.lower() in ["wild", "chaos"]:
            self.wild = True
            self.spells = []
            return
        else:
            self.wild = False

        spellset = spellsets[spellclass]
        spellset = sorted([s for s in spellset if s in valid_spells],
                          key=lambda s: s.spellid)
        if len(spellset) < 3:
            raise ValueError("Spellset %s not big enough." % spellclass)

        for setlength in [8, 16, 32]:
            if len(spellset) <= setlength:
                spells = sorted(spellset)
                while len(spells) < setlength:
                    spells.append(random.choice(spellset))
                break
        else:
            assert setlength == 32
            spells = random.sample(sorted(spellset),
                                   min(setlength, len(spellset)))
            while len(spells) < setlength:
                spells.append(random.choice(spellset))
            assert len(set(spells)) > 16

        self.spells = sorted(spells)

        return self.spells


class MultipleSpellSub(Substitution):
    @property
    def size(self):
        overhead = (self.count * 3) + 1
        return self.spellsub.size + overhead

    def set_count(self, count):
        self.count = count

    def set_spells(self, spells):
        if isinstance(spells, int):
            self.spellsub = SpellSub(spellid=spells)
        else:
            self.spellsub = RandomSpellSub()
            self.spellsub.set_spells(spells)
            self.name = self.spellsub.name
            self.spells = self.spellsub.spells

    def generate_bytestring(self):
        subpointer = self.location + (self.count * 3) + 1
        self.spellsub.set_location(subpointer)
        if not hasattr(self.spellsub, "bytestring"):
            self.spellsub.generate_bytestring()
        high, low = (subpointer >> 8) & 0xFF, subpointer & 0xFF
        self.bytestring = [0x20, low, high] * self.count
        self.bytestring += [0x60]
        self.bytestring += self.spellsub.bytestring
